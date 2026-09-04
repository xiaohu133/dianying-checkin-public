const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const readline = require('readline');

const wasmPath = path.join(__dirname, 'hdh_security_bg.wasm');
const wasmData = fs.readFileSync(wasmPath);

let wasmInstance, wasmExports;
let heap = new Array(1024).fill(undefined);
heap.push(undefined, null, true, false);
let heap_next = heap.length;

function addHeapObject(obj) {
    if (heap_next === heap.length) heap.push(heap.length + 1);
    const idx = heap_next;
    heap_next = heap[idx];
    heap[idx] = obj;
    return idx;
}
function getObject(idx) { return heap[idx]; }
function dropObject(idx) {
    if (idx < 1028) return;
    heap[idx] = heap_next;
    heap_next = idx;
}
function takeObject(idx) {
    const ret = getObject(idx);
    dropObject(idx);
    return ret;
}

let cachedUint8Memory0 = null;
function getUint8Memory0() {
    if (cachedUint8Memory0 === null || cachedUint8Memory0.byteLength === 0) {
        cachedUint8Memory0 = new Uint8Array(wasmExports.memory.buffer);
    }
    return cachedUint8Memory0;
}

let cachedDataViewMemory0 = null;
function getDataViewMemory0() {
    if (cachedDataViewMemory0 === null || cachedDataViewMemory0.buffer.detached === true || (cachedDataViewMemory0.buffer.detached === undefined && cachedDataViewMemory0.buffer !== wasmExports.memory.buffer)) {
        cachedDataViewMemory0 = new DataView(wasmExports.memory.buffer);
    }
    return cachedDataViewMemory0;
}

const cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
cachedTextDecoder.decode();

function getStringFromWasm0(ptr, len) {
    return cachedTextDecoder.decode(getUint8Memory0().subarray(ptr >>> 0, (ptr >>> 0) + len));
}

let WASM_VECTOR_LEN = 0;
const cachedTextEncoder = new TextEncoder();

function passStringToWasm0(arg, malloc) {
    const buf = cachedTextEncoder.encode(arg);
    const ptr = malloc(buf.length, 1) >>> 0;
    getUint8Memory0().subarray(ptr, ptr + buf.length).set(buf);
    WASM_VECTOR_LEN = buf.length;
    return ptr;
}

function passArray8ToWasm0(arg, malloc) {
    const ptr = malloc(arg.length * 1, 1) >>> 0;
    getUint8Memory0().set(arg, ptr / 1);
    WASM_VECTOR_LEN = arg.length;
    return ptr;
}

function getArrayU8FromWasm0(ptr, len) {
    return getUint8Memory0().subarray((ptr >>> 0) / 1, (ptr >>> 0) / 1 + len);
}

const imports = {
    "./hdh_security_bg.js": {
        __wbg_randomFillSync_6c25eac9869eb53c: (arg0, arg1) => crypto.randomFillSync(takeObject(arg1)),
        __wbindgen_object_drop_ref: (arg0) => { takeObject(arg0); },
        __wbg_getRandomValues_c44a50d8cfdaebeb: (arg0, arg1) => getObject(arg0).getRandomValues(getObject(arg1)),
        __wbg_crypto_38df2bab126b63dc: (arg0) => addHeapObject(crypto.webcrypto),
        __wbg_process_44c7a14e11e9f69e: (arg0) => addHeapObject(process),
        __wbg_versions_276b2795b1c6a219: (arg0) => addHeapObject(process.versions),
        __wbg_node_84ea875411254db1: (arg0) => addHeapObject(process.versions.node),
        __wbg_msCrypto_bd5a034af96bcba6: (arg0) => addHeapObject(null),
        __wbg_require_b4edbdcf3e2a1ef0: () => addHeapObject(require),
        __wbg_call_35dba3c747ad7521: (arg0, arg1, arg2) => addHeapObject(getObject(arg0).call(getObject(arg1), getObject(arg2))),
        __wbindgen_object_clone_ref: (arg0) => addHeapObject(getObject(arg0)),
        __wbg_length_36bd29c6848c2144: (arg0) => getObject(arg0).length,
        __wbg_prototypesetcall_de8e0d9553586985: (arg0, arg1, arg2) => {
            Uint8Array.prototype.set.call(getArrayU8FromWasm0(arg0, arg1), getObject(arg2));
        },
        __wbg_new_with_length_3ffc1c56427c525c: (arg0) => addHeapObject(new Uint8Array(arg0 >>> 0)),
        __wbg_subarray_a4cc58201c7359fd: (arg0, arg1, arg2) => addHeapObject(getObject(arg0).subarray(arg1 >>> 0, arg2 >>> 0)),
        __wbg_static_accessor_GLOBAL_THIS_466428f93b4eaa76: () => addHeapObject(globalThis),
        __wbg_static_accessor_SELF_42d4fae05e59267a: () => 0,
        __wbg_static_accessor_GLOBAL_c7aea38d4de089bc: () => addHeapObject(global),
        __wbg_static_accessor_WINDOW_e0db14a0eba6a812: () => 0,
        __wbg___wbindgen_throw_bb96b2010945f0bc: (arg0, arg1) => { throw new Error(getStringFromWasm0(arg0, arg1)); },
        __wbg_Error_408e67f47ca7b58b: (arg0, arg1) => addHeapObject(new Error(getStringFromWasm0(arg0, arg1))),
        __wbg___wbindgen_is_object_a2790eb24c211ea0: (arg0) => typeof(getObject(arg0)) === 'object' && getObject(arg0) !== null,
        __wbg___wbindgen_is_string_e6f02f0ea5f20a32: (arg0) => typeof(getObject(arg0)) === 'string',
        __wbg___wbindgen_is_function_5e4570eb24ffa122: (arg0) => typeof(getObject(arg0)) === 'function',
        __wbg___wbindgen_is_undefined_6cff064c44e0d823: (arg0) => getObject(arg0) === undefined,
        __wbindgen_cast_0000000000000001: (arg0, arg1) => addHeapObject(getArrayU8FromWasm0(arg0, arg1)),
        __wbindgen_cast_0000000000000002: (arg0, arg1) => addHeapObject(getStringFromWasm0(arg0, arg1))
    }
};

function ensureWasm() {
    if (wasmInstance) return;
    const wasmModule = new WebAssembly.Module(wasmData);
    wasmInstance = new WebAssembly.Instance(wasmModule, imports);
    wasmExports = wasmInstance.exports;
}

function initWasm() {
    ensureWasm();
    const retptr = wasmExports.__wbindgen_add_to_stack_pointer(-16);
    wasmExports.init(retptr);
    const r0 = getDataViewMemory0().getInt32(retptr + 0, true);
    const r1 = getDataViewMemory0().getInt32(retptr + 4, true);
    const r2 = getDataViewMemory0().getInt32(retptr + 8, true);
    const r3 = getDataViewMemory0().getInt32(retptr + 12, true);
    wasmExports.__wbindgen_add_to_stack_pointer(16);
    if (r3) throw takeObject(r2);
    const client_pub = getArrayU8FromWasm0(r0, r1).slice();
    wasmExports.__wbindgen_export3(r0, r1, 1);
    return client_pub;
}

function finalizeHandshake(cid, server_pub_bytes, kid = 1) {
    ensureWasm();
    const retptr = wasmExports.__wbindgen_add_to_stack_pointer(-16);
    const ptr0 = passStringToWasm0(cid, wasmExports.__wbindgen_export2);
    const len0 = WASM_VECTOR_LEN;
    const ptr1 = passArray8ToWasm0(server_pub_bytes, wasmExports.__wbindgen_export2);
    const len1 = WASM_VECTOR_LEN;

    wasmExports.finalizeHandshake(retptr, ptr0, len0, ptr1, len1, kid);
    const r0 = getDataViewMemory0().getInt32(retptr + 0, true);
    const r1 = getDataViewMemory0().getInt32(retptr + 4, true);
    wasmExports.__wbindgen_add_to_stack_pointer(16);
    if (r1) throw takeObject(r0);
}

function signRequest(method, path, ts, nonce, bodyBytes, actionProof = "0") {
    ensureWasm();
    let deferredA, deferredC;
    try {
        const retptr = wasmExports.__wbindgen_add_to_stack_pointer(-16);
        const ptrM = passStringToWasm0(method, wasmExports.__wbindgen_export2);
        const lenM = WASM_VECTOR_LEN;
        const ptrP = passStringToWasm0(path, wasmExports.__wbindgen_export2);
        const lenP = WASM_VECTOR_LEN;
        const ptrT = passStringToWasm0(ts, wasmExports.__wbindgen_export2);
        const lenT = WASM_VECTOR_LEN;
        const ptrN = passStringToWasm0(nonce, wasmExports.__wbindgen_export2);
        const lenN = WASM_VECTOR_LEN;
        const ptrB = passArray8ToWasm0(bodyBytes, wasmExports.__wbindgen_export2);
        const lenB = WASM_VECTOR_LEN;
        const ptrA = passStringToWasm0(actionProof, wasmExports.__wbindgen_export2);
        const lenA = WASM_VECTOR_LEN;

        wasmExports.signRequest(retptr, ptrM, lenM, ptrP, lenP, ptrT, lenT, ptrN, lenN, ptrB, lenB, ptrA, lenA);
        const r0 = getDataViewMemory0().getInt32(retptr + 0, true);
        const r1 = getDataViewMemory0().getInt32(retptr + 4, true);
        const r2 = getDataViewMemory0().getInt32(retptr + 8, true);
        const r3 = getDataViewMemory0().getInt32(retptr + 12, true);
        if (r3) throw takeObject(r2);
        deferredA = r0;
        deferredC = r1;
        return getStringFromWasm0(r0, r1);
    } finally {
        wasmExports.__wbindgen_add_to_stack_pointer(16);
        if (deferredA !== undefined) wasmExports.__wbindgen_export3(deferredA, deferredC, 1);
    }
}

function solvePoW(clientPubB64, ts, bits = 16) {
    const prefix = `${clientPubB64}:${ts}:`;
    const targetHexChars = Math.floor(bits / 4);
    const requiredPrefix = "0".repeat(targetHexChars);

    for (let i = 0; i < 0x7fffffff; i++) {
        const nonce = i.toString(36);
        const hash = crypto.createHash('sha256').update(prefix + nonce).digest('hex');
        if (hash.startsWith(requiredPrefix)) return nonce;
    }
    throw new Error("PoW failed");
}

// Session state maintained in process
let currentSession = null;

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

rl.on('line', (line) => {
    line = line.trim();
    if (!line) return;
    try {
        const req = JSON.parse(line);
        const action = req.action;

        if (action === "init_handshake") {
            const userAgent = req.userAgent || "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
            const languages = "zh-CN,zh";
            const clientPub = initWasm();
            const clientPubB64 = Buffer.from(clientPub).toString('base64');
            const ts = Date.now();
            const powNonce = solvePoW(clientPubB64, ts, 16);
            const uaFingerprint = crypto.createHash('sha256').update(`${userAgent}|${languages}`).digest('hex');

            console.log(JSON.stringify({
                success: true,
                payload: {
                    client_pub: clientPubB64,
                    ua_fingerprint: uaFingerprint,
                    ts: ts,
                    bind_token: "",
                    pow_nonce: powNonce
                }
            }));
        } else if (action === "finalize_handshake") {
            const { cid, server_pub, expires_at } = req;
            finalizeHandshake(cid, Buffer.from(server_pub, 'base64'), 1);
            currentSession = { cid, server_pub, expires_at };
            console.log(JSON.stringify({ success: true }));
        } else if (action === "sign") {
            if (!currentSession) {
                console.log(JSON.stringify({ success: false, error: "No active handshake session" }));
                return;
            }
            const method = (req.method || "GET").toUpperCase();
            const reqPath = req.path || "/api/customer/user/current";
            const userId = String(req.userId || "0");
            const bodyStr = req.body || "";
            const bodyBytes = bodyStr ? Buffer.from(bodyStr, 'utf-8') : new Uint8Array(0);

            const reqTs = Date.now().toString();
            const reqNonce = crypto.randomBytes(16).toString('hex');
            const sig = signRequest(method, reqPath, reqTs, reqNonce, bodyBytes, userId);

            console.log(JSON.stringify({
                success: true,
                headers: {
                    "X-HDH-Cid": currentSession.cid,
                    "X-HDH-TS": reqTs,
                    "X-HDH-Nonce": reqNonce,
                    "X-HDH-Sig": sig,
                    "X-HDH-Kid": "1"
                }
            }));
        } else if (action === "ping") {
            console.log(JSON.stringify({ success: true, message: "pong" }));
        } else {
            console.log(JSON.stringify({ success: false, error: `Unknown action: ${action}` }));
        }
    } catch (err) {
        console.log(JSON.stringify({ success: false, error: err.message || String(err) }));
    }
});
