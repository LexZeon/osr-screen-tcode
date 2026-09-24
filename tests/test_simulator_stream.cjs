// Exercise the shipped message/animation code without a browser or WebGL.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../src/osr_screen_tcode/assets/osr_emu_standalone.html'), 'utf8');
const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)];
const application = scripts.at(-1)[1];
const writes = [], sockets = [], frames = [], elements = new Map();
const vector = () => ({clone: vector, sub() { return this; }, multiplyScalar() { return this; }});
const element = () => ({value: 'ws://127.0.0.1:9090/osr-preview', style: {}, clientWidth: 800,
    clientHeight: 600, offsetHeight: 40, classList: {toggle() {}}, addEventListener() {},
    getBoundingClientRect: () => ({height: 60})});
class Socket {
    constructor(url) { this.url = url; sockets.push(this); }
    send() {}
    close() {}
}
class Emulator {
    constructor() {
        this.controls = {target: vector(), update() {}};
        this.camera = {position: {clone: vector, copy: () => ({add() {}})}, updateProjectionMatrix() {}};
    }
    write(command) { writes.push(command); }
}
const context = vm.createContext({OSREmulator: Emulator, WebSocket: Socket,
    window: {innerHeight: 760, addEventListener() {}},
    document: {getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); }},
    console: {log() {}, warn(error) { throw error; }, error(error) { throw error; }},
    showDeviceContext() {}, setInterval() {}, clearInterval() {}, setTimeout() {},
    requestAnimationFrame(callback) { frames.push(callback); return frames.length; }});
vm.runInContext(application, context, {timeout: 2000});
sockets[0].onopen();
const receive = (name, data) => sockets[0].onmessage({data: JSON.stringify({type: 'event', name, data})});
const finalCommand = 'L03400I24 L14240I24 L28040I24 R06200I24 R15000I24 R25000I24';
receive('tcode', {cmd: finalCommand});
assert.equal(writes.at(-1), finalCommand + '\n');
const count = writes.length;
for (let i = 0; i < 100; i++) frames.shift()();
receive('time_change', {time: 42});
receive('project_change', {});
frames.shift()();
assert.equal(writes.length, count, 'OFS/default animation must not replace a final TCode command');
receive('tcode', {cmd: 'L04900I24 L14900I24'});
assert.equal(writes.at(-1), 'L04900I24 L14900I24\n');
sockets[0].onclose({code: 1000});
frames.shift()();
assert.equal(writes.at(-1), 'L04900I24 L14900I24\n');
console.log('Simulator stream check passed: final commands preserved; animation cannot override them.');
