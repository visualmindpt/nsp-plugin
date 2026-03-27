-- json.lua
-- Minimal JSON encode/decode helper (subset of dkjson functionality).
-- Supports tables (objects/arrays), strings, numbers, booleans and null.
-- MIT License.

local json = {}

local escape_char_map = {
    ['"']  = '\\"',
    ['\\'] = '\\\\',
    ['\b'] = '\\b',
    ['\f'] = '\\f',
    ['\n'] = '\\n',
    ['\r'] = '\\r',
    ['\t'] = '\\t',
}

local escape_char_map_inv = { ['\\'] = '\\', ['"'] = '"', ['/'] = '/', ['b'] = '\b', ['f'] = '\f', ['n'] = '\n', ['r'] = '\r', ['t'] = '\t' }

local function escape_char(c)
    return escape_char_map[c] or string.format("\\u%04x", c:byte())
end

local function encode_string(value)
    return '"' .. value:gsub('[%z\1-\31\\"]', escape_char) .. '"'
end

local function is_array(tbl)
    local max = 0
    local count = 0
    for k, _ in pairs(tbl) do
        if type(k) == "number" then
            if k > max then
                max = k
            end
            count = count + 1
        else
            return false
        end
    end
    return max == count
end

local encode_value

local function encode_object(tbl)
    local result = {}
    for k, v in pairs(tbl) do
        table.insert(result, encode_string(tostring(k)) .. ":" .. encode_value(v))
    end
    return "{" .. table.concat(result, ",") .. "}"
end

local function encode_array(tbl)
    local result = {}
    for i = 1, #tbl do
        table.insert(result, encode_value(tbl[i]))
    end
    return "[" .. table.concat(result, ",") .. "]"
end

encode_value = function(value)
    local t = type(value)
    if t == "string" then
        return encode_string(value)
    elseif t == "number" then
        return tostring(value)
    elseif t == "boolean" then
        return value and "true" or "false"
    elseif t == "table" then
        if next(value) == nil then
            return "{}"
        elseif is_array(value) then
            return encode_array(value)
        else
            return encode_object(value)
        end
    elseif t == "nil" then
        return "null"
    else
        error("unsupported type in JSON: " .. t)
    end
end

function json.encode(value)
    return encode_value(value)
end

local function decode_error(str, idx, msg)
    error(string.format("JSON decode error at position %d: %s", idx, msg))
end

local function skip_whitespace(str, idx)
    local _, next_index = str:find("^[ \n\r\t]*", idx)
    return (next_index or idx - 1) + 1
end

local decode_value

local function decode_string(str, idx)
    idx = idx + 1
    local result = {}
    while idx <= #str do
        local c = str:sub(idx, idx)
        if c == '"' then
            return table.concat(result), idx + 1
        elseif c == '\\' then
            local next_char = str:sub(idx + 1, idx + 1)
            local escaped = escape_char_map_inv[next_char]
            if escaped then
                table.insert(result, escaped)
                idx = idx + 2
            elseif next_char == "u" then
                local hex = str:sub(idx + 2, idx + 5)
                if not hex:match("%x%x%x%x") then
                    decode_error(str, idx, "invalid unicode escape")
                end
                local codepoint = tonumber(hex, 16) or 63
                if codepoint <= 0xFF then
                    table.insert(result, string.char(codepoint))
                else
                    -- For Lightroom's Lua (5.1) sem suporte UTF-8 nativo,
                    -- devolvemos um ponto de interrogação como fallback.
                    table.insert(result, "?")
                end
                idx = idx + 6
            else
                decode_error(str, idx, "invalid escape")
            end
        else
            table.insert(result, c)
            idx = idx + 1
        end
    end
    decode_error(str, idx, "unterminated string")
end

local function decode_number(str, idx)
    local num_str = str:match("^%-?%d+%.?%d*[eE]?[%+%-]?%d*", idx)
    if not num_str then
        decode_error(str, idx, "invalid number")
    end
    return tonumber(num_str), idx + #num_str
end

local function decode_literal(str, idx, literal, value)
    if str:sub(idx, idx + #literal - 1) == literal then
        return value, idx + #literal
    end
    decode_error(str, idx, "invalid literal")
end

local function decode_array(str, idx)
    idx = idx + 1
    local result = {}
    idx = skip_whitespace(str, idx)
    if str:sub(idx, idx) == "]" then
        return result, idx + 1
    end
    while true do
        local value
        value, idx = decode_value(str, idx)
        table.insert(result, value)
        idx = skip_whitespace(str, idx)
        local char = str:sub(idx, idx)
        if char == "]" then
            return result, idx + 1
        elseif char ~= "," then
            decode_error(str, idx, "expected ',' or ']'")
        end
        idx = skip_whitespace(str, idx + 1)
    end
end

local function decode_object(str, idx)
    idx = idx + 1
    local result = {}
    idx = skip_whitespace(str, idx)
    if str:sub(idx, idx) == "}" then
        return result, idx + 1
    end
    while true do
        local key
        key, idx = decode_string(str, idx)
        idx = skip_whitespace(str, idx)
        if str:sub(idx, idx) ~= ":" then
            decode_error(str, idx, "expected ':' after key")
        end
        idx = skip_whitespace(str, idx + 1)
        local value
        value, idx = decode_value(str, idx)
        result[key] = value
        idx = skip_whitespace(str, idx)
        local char = str:sub(idx, idx)
        if char == "}" then
            return result, idx + 1
        elseif char ~= "," then
            decode_error(str, idx, "expected ',' or '}'")
        end
        idx = skip_whitespace(str, idx + 1)
    end
end

decode_value = function(str, idx)
    idx = skip_whitespace(str, idx)
    local char = str:sub(idx, idx)
    if char == '"' then
        return decode_string(str, idx)
    elseif char == "-" or char:match("%d") then
        return decode_number(str, idx)
    elseif char == "{" then
        return decode_object(str, idx)
    elseif char == "[" then
        return decode_array(str, idx)
    elseif char == "t" then
        return decode_literal(str, idx, "true", true)
    elseif char == "f" then
        return decode_literal(str, idx, "false", false)
    elseif char == "n" then
        return decode_literal(str, idx, "null", nil)
    elseif char == "" then
        decode_error(str, idx, "unexpected end of input")
    else
        decode_error(str, idx, "unexpected character '" .. char .. "'")
    end
end

function json.decode(str)
    if type(str) ~= "string" then
        error("JSON decode expects a string")
    end
    local result, idx = decode_value(str, 1)
    idx = skip_whitespace(str, idx)
    if idx <= #str then
        decode_error(str, idx, "trailing characters")
    end
    return result
end

return json
