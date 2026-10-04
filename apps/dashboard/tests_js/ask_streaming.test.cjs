const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/dashboard/js/dashboard.js'), 'utf8');
const helper = source.slice(source.indexOf('    async function readAssistantResponse'), source.indexOf('    assistants.forEach'));
const read = new Function(helper + '; return readAssistantResponse;')();
function response(text, split) {
    const bytes = new TextEncoder().encode(text);
    return new Response(new ReadableStream({start(controller) {
        for (let i = 0; i < bytes.length; i += split) controller.enqueue(bytes.slice(i, i + split));
        controller.close();
    }}), {headers: {'Content-Type': 'text/event-stream'}});
}
test('split UTF-8 and SSE boundaries preserve complete answer and progress', async () => {
    let progress = 0;
    const text = 'event: accepted\ndata: {"ok":true}\n\nevent: progress\ndata: {"elapsed_seconds":10}\n\nevent: result\ndata: {"ok":true,"answer":"الدليل والقيود"}\n\n';
    const payload = await read(response(text, 1), () => progress++);
    assert.equal(payload.answer, 'الدليل والقيود');
    assert.equal(progress, 2);
});
test('multiple frames in one chunk return terminal provider failure', async () => {
    const payload = await read(response('event: accepted\ndata: {"ok":true}\n\nevent: error\ndata: {"ok":false,"status":503}\n\n', 4096), () => {});
    assert.equal(payload.ok, false);
    assert.equal(payload.status, 503);
});
test('EOF without terminal event is failure, never an empty success', async () => {
    await assert.rejects(read(response('event: accepted\ndata: {"ok":true}\n\n', 4096), () => {}));
});
test('Marketing and preflight JSON response remain supported', async () => {
    const payload = await read(new Response('{"ok":true,"answer":"Marketing"}', {headers: {'Content-Type':'application/json'}}), () => assert.fail());
    assert.equal(payload.answer, 'Marketing');
});
test('malformed stream fails safely', async () => {
    await assert.rejects(read(response('event: result\ndata: invalid\n\n', 4096), () => {}));
});
