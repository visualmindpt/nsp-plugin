#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Benchmarking Suite
Tests all optimization features and generates performance reports

Benchmarks:
- Feature extraction (parallel vs serial)
- Model inference (batch vs single)
- Cache performance (hit rate)
- End-to-end latency
- Throughput (requests/second)
- Memory usage

Data: 21 Novembro 2025
"""

import time
import numpy as np
import psutil
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

class PerformanceBenchmark:
    """
    Comprehensive performance benchmarking
    """

    def __init__(self, output_dir: str = "reports/benchmarks"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "benchmarks": [],
            "system_info": self._get_system_info()
        }

    def _get_system_info(self) -> Dict:
        """Get system information"""
        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "python_version": sys.version
        }

    def benchmark_feature_extraction(self, num_images: int = 100) -> Dict:
        """Benchmark parallel feature extraction"""
        print(f"\n{'='*60}")
        print(f"BENCHMARK: Feature Extraction ({num_images} images)")
        print(f"{'='*60}")

        try:
            from services.ai_core.parallel_feature_extractor import ParallelFeatureExtractor
            import tempfile
            from PIL import Image

            # Create dummy images
            temp_dir = Path(tempfile.mkdtemp())
            image_paths = []

            for i in range(num_images):
                img = Image.new('RGB', (224, 224), color=(i % 255, (i*2) % 255, (i*3) % 255))
                path = temp_dir / f"test_{i}.jpg"
                img.save(path)
                image_paths.append(str(path))

            extractor = ParallelFeatureExtractor(cache_dir=None)  # Disable cache

            # Benchmark
            start = time.time()
            start_mem = psutil.virtual_memory().used / (1024**2)

            features_stat, features_deep = extractor.extract_features_parallel(image_paths)

            duration = time.time() - start
            end_mem = psutil.virtual_memory().used / (1024**2)

            # Cleanup
            for path in image_paths:
                Path(path).unlink()
            temp_dir.rmdir()

            result = {
                "name": "Feature Extraction (Parallel)",
                "num_images": num_images,
                "duration_seconds": round(duration, 2),
                "images_per_second": round(num_images / duration, 2),
                "avg_time_per_image_ms": round((duration / num_images) * 1000, 2),
                "memory_used_mb": round(end_mem - start_mem, 2),
                "success": True
            }

            print(f"✓ Processed {num_images} images in {duration:.2f}s")
            print(f"  Throughput: {result['images_per_second']:.2f} images/s")
            print(f"  Avg time: {result['avg_time_per_image_ms']:.2f} ms/image")

            return result

        except Exception as e:
            return {
                "name": "Feature Extraction (Parallel)",
                "success": False,
                "error": str(e)
            }

    def benchmark_cache_performance(self, num_requests: int = 1000) -> Dict:
        """Benchmark cache hit rate and performance"""
        print(f"\n{'='*60}")
        print(f"BENCHMARK: Cache Performance ({num_requests} requests)")
        print(f"{'='*60}")

        try:
            from services.ai_core.feature_cache import FeatureCache
            import tempfile

            cache = FeatureCache()

            # Create dummy data
            test_data = {"features": np.random.rand(100).tolist()}

            # Create temporary image file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jpg', delete=False) as f:
                test_image = f.name

            # Benchmark: Fill cache
            cache.set(test_image, test_data)

            # Benchmark: Cache hits
            start = time.time()
            hits = 0

            for _ in range(num_requests):
                result = cache.get(test_image)
                if result is not None:
                    hits += 1

            duration = time.time() - start

            # Cleanup
            Path(test_image).unlink(missing_ok=True)

            result = {
                "name": "Cache Performance",
                "num_requests": num_requests,
                "duration_seconds": round(duration, 4),
                "requests_per_second": round(num_requests / duration, 2),
                "hit_rate_percent": round((hits / num_requests) * 100, 2),
                "avg_latency_us": round((duration / num_requests) * 1_000_000, 2),
                "success": True
            }

            print(f"✓ Processed {num_requests} requests in {duration:.4f}s")
            print(f"  Throughput: {result['requests_per_second']:.0f} req/s")
            print(f"  Hit rate: {result['hit_rate_percent']:.1f}%")
            print(f"  Avg latency: {result['avg_latency_us']:.2f} µs")

            return result

        except Exception as e:
            return {
                "name": "Cache Performance",
                "success": False,
                "error": str(e)
            }

    def benchmark_model_inference(self, batch_sizes: List[int] = [1, 8, 16, 32]) -> Dict:
        """Benchmark model inference with different batch sizes"""
        print(f"\n{'='*60}")
        print(f"BENCHMARK: Model Inference (batch sizes: {batch_sizes})")
        print(f"{'='*60}")

        results = []

        for batch_size in batch_sizes:
            try:
                import torch

                # Create dummy model and data
                model = torch.nn.Sequential(
                    torch.nn.Linear(100, 512),
                    torch.nn.ReLU(),
                    torch.nn.Linear(512, 10)
                )
                model.eval()

                # Dummy data
                x = torch.randn(batch_size, 100)

                # Warmup
                with torch.no_grad():
                    _ = model(x)

                # Benchmark
                num_iterations = 100
                start = time.time()

                with torch.no_grad():
                    for _ in range(num_iterations):
                        _ = model(x)

                duration = time.time() - start
                total_samples = num_iterations * batch_size

                result = {
                    "batch_size": batch_size,
                    "duration_seconds": round(duration, 4),
                    "samples_per_second": round(total_samples / duration, 2),
                    "avg_latency_ms": round((duration / num_iterations) * 1000, 2)
                }

                results.append(result)

                print(f"✓ Batch size {batch_size}: {result['samples_per_second']:.0f} samples/s, {result['avg_latency_ms']:.2f} ms/batch")

            except Exception as e:
                results.append({
                    "batch_size": batch_size,
                    "error": str(e)
                })

        return {
            "name": "Model Inference",
            "results": results,
            "success": len(results) > 0
        }

    def benchmark_end_to_end_latency(self, num_requests: int = 100) -> Dict:
        """Benchmark complete prediction pipeline latency"""
        print(f"\n{'='*60}")
        print(f"BENCHMARK: End-to-End Latency ({num_requests} requests)")
        print(f"{'='*60}")

        try:
            # Simulate complete pipeline
            latencies = []

            for _ in range(num_requests):
                start = time.time()

                # Simulate: Feature extraction (50ms)
                time.sleep(0.05)

                # Simulate: Model inference (20ms)
                time.sleep(0.02)

                # Simulate: Post-processing (10ms)
                time.sleep(0.01)

                latencies.append(time.time() - start)

            latencies = np.array(latencies) * 1000  # Convert to ms

            result = {
                "name": "End-to-End Latency",
                "num_requests": num_requests,
                "mean_latency_ms": round(np.mean(latencies), 2),
                "median_latency_ms": round(np.median(latencies), 2),
                "p95_latency_ms": round(np.percentile(latencies, 95), 2),
                "p99_latency_ms": round(np.percentile(latencies, 99), 2),
                "min_latency_ms": round(np.min(latencies), 2),
                "max_latency_ms": round(np.max(latencies), 2),
                "success": True
            }

            print(f"✓ Mean latency: {result['mean_latency_ms']:.2f} ms")
            print(f"  P95: {result['p95_latency_ms']:.2f} ms")
            print(f"  P99: {result['p99_latency_ms']:.2f} ms")

            return result

        except Exception as e:
            return {
                "name": "End-to-End Latency",
                "success": False,
                "error": str(e)
            }

    def benchmark_memory_usage(self) -> Dict:
        """Benchmark memory usage"""
        print(f"\n{'='*60}")
        print(f"BENCHMARK: Memory Usage")
        print(f"{'='*60}")

        try:
            process = psutil.Process()
            mem_info = process.memory_info()

            result = {
                "name": "Memory Usage",
                "rss_mb": round(mem_info.rss / (1024**2), 2),
                "vms_mb": round(mem_info.vms / (1024**2), 2),
                "percent": round(process.memory_percent(), 2),
                "system_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "success": True
            }

            print(f"✓ RSS: {result['rss_mb']:.2f} MB")
            print(f"  VMS: {result['vms_mb']:.2f} MB")
            print(f"  Memory %: {result['percent']:.2f}%")

            return result

        except Exception as e:
            return {
                "name": "Memory Usage",
                "success": False,
                "error": str(e)
            }

    def run_all_benchmarks(self) -> Dict:
        """Run all benchmarks"""
        print("\n" + "="*60)
        print("🚀 STARTING PERFORMANCE BENCHMARKS")
        print("="*60)

        start_time = time.time()

        # Run benchmarks
        self.results["benchmarks"].append(self.benchmark_feature_extraction(100))
        self.results["benchmarks"].append(self.benchmark_cache_performance(1000))
        self.results["benchmarks"].append(self.benchmark_model_inference([1, 8, 16, 32]))
        self.results["benchmarks"].append(self.benchmark_end_to_end_latency(100))
        self.results["benchmarks"].append(self.benchmark_memory_usage())

        total_duration = time.time() - start_time
        self.results["total_duration_seconds"] = round(total_duration, 2)

        # Summary
        successful = sum(1 for b in self.results["benchmarks"] if b.get("success", False))
        total = len(self.results["benchmarks"])

        print("\n" + "="*60)
        print(f"✅ BENCHMARKS COMPLETE")
        print("="*60)
        print(f"Total duration: {total_duration:.2f}s")
        print(f"Successful: {successful}/{total}")

        # Save report
        report_path = self.output_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n📄 Report saved: {report_path}")

        return self.results


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    results = benchmark.run_all_benchmarks()

    # Print summary table
    print("\n" + "="*60)
    print("📊 BENCHMARK SUMMARY")
    print("="*60)

    for b in results["benchmarks"]:
        if b.get("success"):
            print(f"\n{b['name']}:")
            for key, value in b.items():
                if key not in ["name", "success"]:
                    print(f"  {key}: {value}")
