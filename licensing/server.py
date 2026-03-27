"""
licensing/server.py

License Server for NSP Plugin - Production-ready licensing system.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from jose import JWTError, jwt
from passlib.context import CryptContext
import logging
import stripe

# Configuration
import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nsp_licensing.db")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Email Configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@vilearn.ai")

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="NSP License Server", version="1.0.0")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# DATABASE MODELS
# ============================================================================

class License(Base):
    __tablename__ = "licenses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    license_key = Column(String(32), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    plan = Column(String(50), nullable=False)  # trial, personal, professional, studio
    status = Column(String(20), default="active")  # active, expired, revoked
    max_activations = Column(Integer, default=2)
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoke_reason = Column(String(500), nullable=True)
    license_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class Activation(Base):
    __tablename__ = "activations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    license_id = Column(String(36), nullable=False, index=True)
    machine_id = Column(String(64), nullable=False)
    machine_name = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    activated_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    deactivated_at = Column(DateTime, nullable=True)


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    activation_id = Column(String(36), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String(45), nullable=True)
    plugin_version = Column(String(20), nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ActivateRequest(BaseModel):
    license_key: str = Field(..., min_length=20, max_length=32)
    machine_id: str = Field(..., min_length=32, max_length=64)
    machine_name: Optional[str] = None


class ActivateResponse(BaseModel):
    success: bool
    token: str
    plan: str
    expires_at: Optional[datetime]
    features: dict


class ValidateRequest(BaseModel):
    token: str


class ValidateResponse(BaseModel):
    valid: bool
    plan: str
    expires_at: Optional[datetime]
    days_remaining: Optional[int]


class HeartbeatRequest(BaseModel):
    token: str
    plugin_version: str = "2.0.0"


class DeactivateRequest(BaseModel):
    token: str


class CreateLicenseRequest(BaseModel):
    email: EmailStr
    plan: str = Field(..., pattern="^(trial|personal|professional|studio)$")
    max_activations: int = Field(default=2, ge=1, le=100)
    duration_days: Optional[int] = None  # None = perpetual


# ============================================================================
# DEPENDENCIES
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_license_key() -> str:
    """Generate unique license key: VELA-XXXX-XXXX-XXXX-XXXX"""
    parts = []
    for _ in range(4):
        part = secrets.token_hex(2).upper()
        parts.append(part)

    key = f"VELA-{'-'.join(parts)}"
    return key


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_feature_set(plan: str) -> dict:
    """Return available features for plan."""
    features = {
        "trial": {
            "lightgbm": True,
            "neural_network": False,
            "smart_culling": False,
            "auto_profiling": False,
            "max_photos_per_batch": 50,
        },
        "personal": {
            "lightgbm": True,
            "neural_network": True,
            "smart_culling": True,
            "auto_profiling": False,
            "max_photos_per_batch": 500,
        },
        "professional": {
            "lightgbm": True,
            "neural_network": True,
            "smart_culling": True,
            "auto_profiling": True,
            "max_photos_per_batch": 5000,
        },
        "studio": {
            "lightgbm": True,
            "neural_network": True,
            "smart_culling": True,
            "auto_profiling": True,
            "max_photos_per_batch": -1,  # Unlimited
        },
    }

    return features.get(plan, features["trial"])


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "nsp-license-server", "version": "1.0.0"}


@app.post("/api/v1/licenses/create", response_model=dict)
def create_license(
    request: CreateLicenseRequest,
    db: Session = Depends(get_db),
    x_admin_key: str = Header(None)
):
    """
    Admin endpoint to create new license.
    Requires X-Admin-Key header.
    """
    # TODO: Implement proper admin authentication
    if x_admin_key != "admin_secret_key_change_me":
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Generate unique license key
    license_key = generate_license_key()

    # Calculate expiration
    expires_at = None
    if request.duration_days:
        expires_at = datetime.utcnow() + timedelta(days=request.duration_days)

    # Create license
    license_obj = License(
        license_key=license_key,
        email=request.email,
        plan=request.plan,
        max_activations=request.max_activations,
        expires_at=expires_at,
    )

    db.add(license_obj)
    db.commit()

    logger.info(f"Created license {license_key} for {request.email} (plan: {request.plan})")

    return {
        "success": True,
        "license_key": license_key,
        "email": request.email,
        "plan": request.plan,
        "expires_at": expires_at,
    }


@app.post("/api/v1/licenses/activate", response_model=ActivateResponse)
def activate_license(
    request: ActivateRequest,
    db: Session = Depends(get_db),
    x_forwarded_for: str = Header(None)
):
    """Activate license on a new machine."""

    # Find license
    license_obj = db.query(License).filter(License.license_key == request.license_key).first()

    if not license_obj:
        raise HTTPException(status_code=404, detail="License key not found")

    # Check license status
    if license_obj.status == "revoked":
        raise HTTPException(
            status_code=403,
            detail=f"License revoked: {license_obj.revoke_reason or 'No reason provided'}"
        )

    if license_obj.status == "expired":
        raise HTTPException(status_code=403, detail="License has expired")

    # Check expiration
    if license_obj.expires_at and license_obj.expires_at < datetime.utcnow():
        license_obj.status = "expired"
        db.commit()
        raise HTTPException(status_code=403, detail="License has expired")

    # Check if machine already activated
    existing_activation = db.query(Activation).filter(
        Activation.license_id == license_obj.id,
        Activation.machine_id == request.machine_id,
        Activation.deactivated_at.is_(None)
    ).first()

    if existing_activation:
        # Already activated - return token
        token_data = {
            "activation_id": existing_activation.id,
            "license_id": license_obj.id,
            "machine_id": request.machine_id,
            "plan": license_obj.plan,
        }
        token = create_access_token(token_data)

        logger.info(f"Re-activated license {request.license_key} on machine {request.machine_id}")

        return ActivateResponse(
            success=True,
            token=token,
            plan=license_obj.plan,
            expires_at=license_obj.expires_at,
            features=get_feature_set(license_obj.plan),
        )

    # Check activation limit
    active_count = db.query(Activation).filter(
        Activation.license_id == license_obj.id,
        Activation.deactivated_at.is_(None)
    ).count()

    if active_count >= license_obj.max_activations:
        raise HTTPException(
            status_code=403,
            detail=f"Maximum activations ({license_obj.max_activations}) reached. Deactivate another machine first."
        )

    # Create new activation
    activation = Activation(
        license_id=license_obj.id,
        machine_id=request.machine_id,
        machine_name=request.machine_name,
        ip_address=x_forwarded_for or "unknown",
    )

    db.add(activation)
    db.commit()

    # Create access token
    token_data = {
        "activation_id": activation.id,
        "license_id": license_obj.id,
        "machine_id": request.machine_id,
        "plan": license_obj.plan,
    }
    token = create_access_token(token_data)

    logger.info(f"Activated license {request.license_key} on machine {request.machine_id}")

    return ActivateResponse(
        success=True,
        token=token,
        plan=license_obj.plan,
        expires_at=license_obj.expires_at,
        features=get_feature_set(license_obj.plan),
    )


@app.post("/api/v1/licenses/validate", response_model=ValidateResponse)
def validate_license(request: ValidateRequest, db: Session = Depends(get_db)):
    """Validate license token."""

    payload = decode_token(request.token)

    activation_id = payload.get("activation_id")
    license_id = payload.get("license_id")

    if not activation_id or not license_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Check activation
    activation = db.query(Activation).filter(Activation.id == activation_id).first()
    if not activation or activation.deactivated_at:
        raise HTTPException(status_code=401, detail="Activation not found or deactivated")

    # Check license
    license_obj = db.query(License).filter(License.id == license_id).first()
    if not license_obj:
        raise HTTPException(status_code=401, detail="License not found")

    if license_obj.status != "active":
        raise HTTPException(status_code=403, detail=f"License is {license_obj.status}")

    # Check expiration
    days_remaining = None
    if license_obj.expires_at:
        if license_obj.expires_at < datetime.utcnow():
            license_obj.status = "expired"
            db.commit()
            raise HTTPException(status_code=403, detail="License expired")

        days_remaining = (license_obj.expires_at - datetime.utcnow()).days

    return ValidateResponse(
        valid=True,
        plan=license_obj.plan,
        expires_at=license_obj.expires_at,
        days_remaining=days_remaining,
    )


@app.post("/api/v1/licenses/heartbeat")
def heartbeat(
    request: HeartbeatRequest,
    db: Session = Depends(get_db),
    x_forwarded_for: str = Header(None)
):
    """Record heartbeat and refresh token."""

    payload = decode_token(request.token)

    activation_id = payload.get("activation_id")
    if not activation_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    activation = db.query(Activation).filter(Activation.id == activation_id).first()
    if not activation:
        raise HTTPException(status_code=404, detail="Activation not found")

    # Update last heartbeat
    activation.last_heartbeat = datetime.utcnow()

    # Record heartbeat
    heartbeat_obj = Heartbeat(
        activation_id=activation_id,
        ip_address=x_forwarded_for or "unknown",
        plugin_version=request.plugin_version,
    )

    db.add(heartbeat_obj)
    db.commit()

    # Generate new token
    new_token = create_access_token({
        "activation_id": activation.id,
        "license_id": activation.license_id,
        "machine_id": activation.machine_id,
        "plan": payload.get("plan"),
    })

    return {"success": True, "token": new_token}


@app.post("/api/v1/licenses/deactivate")
def deactivate_license(request: DeactivateRequest, db: Session = Depends(get_db)):
    """Deactivate license on current machine."""

    payload = decode_token(request.token)

    activation_id = payload.get("activation_id")
    if not activation_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    activation = db.query(Activation).filter(Activation.id == activation_id).first()
    if not activation:
        raise HTTPException(status_code=404, detail="Activation not found")

    if activation.deactivated_at:
        raise HTTPException(status_code=400, detail="Already deactivated")

    # Deactivate
    activation.deactivated_at = datetime.utcnow()
    db.commit()

    logger.info(f"Deactivated license on machine {activation.machine_id}")

    return {"success": True, "message": "License deactivated successfully"}


@app.get("/api/v1/admin/stats")
def get_stats(db: Session = Depends(get_db), x_admin_key: str = Header(None)):
    """Admin endpoint to get licensing statistics."""

    if x_admin_key != "admin_secret_key_change_me":
        raise HTTPException(status_code=403, detail="Unauthorized")

    total_licenses = db.query(License).count()
    active_licenses = db.query(License).filter(License.status == "active").count()
    total_activations = db.query(Activation).filter(Activation.deactivated_at.is_(None)).count()

    # Heartbeats in last 24h
    since = datetime.utcnow() - timedelta(hours=24)
    recent_heartbeats = db.query(Heartbeat).filter(Heartbeat.timestamp >= since).count()

    return {
        "total_licenses": total_licenses,
        "active_licenses": active_licenses,
        "total_activations": total_activations,
        "heartbeats_24h": recent_heartbeats,
    }


# ============================================================================
# STRIPE WEBHOOK & EMAIL AUTOMATION
# ============================================================================

def send_license_email(email: str, license_key: str, plan: str) -> bool:
    """Send license key via email using SendGrid."""

    if not SENDGRID_API_KEY:
        logger.warning(f"SendGrid not configured, skipping email to {email}")
        logger.info(f"License key for {email}: {license_key}")
        return False

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email, To, Content

        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)

        from_email = Email(FROM_EMAIL)
        to_email = To(email)
        subject = f"Your NSP Plugin {plan.title()} License Key"

        features = get_feature_set(plan)
        max_activations = {
            "trial": 1,
            "personal": 2,
            "professional": 3,
            "studio": 10
        }.get(plan, 2)

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">Welcome to NSP Plugin {plan.title()}! 🎉</h2>

            <p>Thank you for your purchase. Your license key is:</p>

            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 2px; margin: 20px 0; color: #1e40af;">
                {license_key}
            </div>

            <h3 style="color: #1e40af;">How to Activate:</h3>
            <ol style="line-height: 1.8;">
                <li>Open Adobe Lightroom Classic</li>
                <li>Go to <strong>File → Plug-in Manager</strong></li>
                <li>Select <strong>NSP Plugin</strong></li>
                <li>Click <strong>Activate License</strong></li>
                <li>Enter your license key: <code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px;">{license_key}</code></li>
            </ol>

            <h3 style="color: #1e40af;">Your Plan Includes:</h3>
            <ul style="line-height: 1.8;">
                <li>✅ LightGBM AI Selection</li>
                <li>✅ Neural Network Rating</li>
                <li>✅ Smart Culling Algorithm</li>
                <li>✅ Auto-Profiling (Style Detection)</li>
                <li>✅ Process up to {features.get('max_photos_per_batch', 'unlimited')} photos per batch</li>
                <li>✅ Activate on {max_activations} computer{"s" if max_activations > 1 else ""}</li>
            </ul>

            <div style="background: #eff6ff; border-left: 4px solid #2563eb; padding: 15px; margin: 20px 0;">
                <p style="margin: 0;"><strong>💡 Need help?</strong> Reply to this email or visit our documentation at <a href="https://docs.vilearn.ai" style="color: #2563eb;">docs.vilearn.ai</a></p>
            </div>

            <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">

            <p style="color: #6b7280; font-size: 12px; line-height: 1.6;">
                This license is registered to: <strong>{email}</strong><br>
                Plan: <strong>{plan.title()}</strong><br>
                Purchase date: <strong>{datetime.utcnow().strftime('%Y-%m-%d')}</strong><br>
                License type: <strong>Perpetual</strong> (no expiration)
            </p>
        </body>
        </html>
        """

        content = Content("text/html", html_content)
        mail = Mail(from_email, to_email, subject, content)

        response = sg.client.mail.send.post(request_body=mail.get())

        if response.status_code >= 400:
            logger.error(f"Failed to send email to {email}: {response.body}")
            return False
        else:
            logger.info(f"License email sent successfully to {email}")
            return True

    except Exception as e:
        logger.error(f"Error sending email to {email}: {str(e)}")
        return False


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook handler.
    Automatically creates license when payment succeeds.

    Setup in Stripe Dashboard:
    1. Developers → Webhooks → Add endpoint
    2. URL: https://license.vilearn.ai/webhook/stripe
    3. Events: checkout.session.completed
    4. Copy webhook secret to STRIPE_WEBHOOK_SECRET env var
    """

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("Stripe webhook secret not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        # Verify webhook signature (CRITICAL for security)
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid Stripe webhook payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid Stripe webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Extract customer info
        customer_email = session["customer_details"]["email"]
        metadata = session.get("metadata", {})
        plan = metadata.get("plan", "personal")

        # Validate plan
        if plan not in ["trial", "personal", "professional", "studio"]:
            logger.error(f"Invalid plan in Stripe metadata: {plan}")
            plan = "personal"

        # Generate license
        license_key = generate_license_key()

        # Determine max_activations based on plan
        max_activations = {
            "trial": 1,
            "personal": 2,
            "professional": 3,
            "studio": 10
        }.get(plan, 2)

        # Create license in database
        license_obj = License(
            license_key=license_key,
            email=customer_email,
            plan=plan,
            max_activations=max_activations,
            expires_at=None,  # Perpetual license
            license_metadata={
                "stripe_session_id": session["id"],
                "stripe_customer_id": session.get("customer"),
                "stripe_payment_intent": session.get("payment_intent"),
                "amount_paid": session["amount_total"],
                "currency": session["currency"],
                "created_via": "stripe_webhook"
            }
        )

        db.add(license_obj)
        db.commit()

        logger.info(
            f"✅ Auto-created license {license_key} for {customer_email} "
            f"via Stripe (plan: {plan}, amount: {session['amount_total']/100} {session['currency'].upper()})"
        )

        # Send email with license key
        email_sent = send_license_email(customer_email, license_key, plan)

        return {
            "status": "success",
            "license_key": license_key,
            "email_sent": email_sent
        }

    # Ignore other event types
    logger.info(f"Received Stripe event: {event['type']} (ignored)")
    return {"status": "ignored", "event_type": event["type"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
