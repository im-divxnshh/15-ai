// Local subset of https://core.telegram.org/bots/api; never uses real tokens.
const http = require('node:http');
const updates = [{update_id: 100, message: {message_id: 1, date: 1794513600, chat: {id: 12345, type: 'private'}, from: {id: 12345, is_bot: false}, text: '/task Write three study tips'}}];
const server = http.createServer((req, res) => {
  const answer = (code, body) => {res.writeHead(code, {'Content-Type': 'application/json'});res.end(JSON.stringify(body));};
  const match = req.url.match(/^\/bot123456:test-token\/([A-Za-z]+)$/);
  if (req.method !== 'POST' || !match) return answer(501, {ok: false, description: 'Outside the local contract subset'});
  const handle = body => {
    const method = match[1];
    if (method === 'getMe') return answer(200, {ok: true, result: {id: 123456, is_bot: true, first_name: 'NOVA', username: 'nova_fixture_bot'}});
    if (method === 'getChat') return answer(200, {ok: true, result: {id: 12345, type: 'private', first_name: 'Fixture'}});
    if (method === 'getWebhookInfo') return answer(200, {ok: true, result: {url: '', has_custom_certificate: false, pending_update_count: 1}});
    if (method === 'getUpdates') {
      if (!Array.isArray(body.allowed_updates) || !body.allowed_updates.includes('message')) return answer(400, {ok: false, description: 'allowed_updates must include message'});
      return answer(200, {ok: true, result: updates.filter(update => update.update_id >= (body.offset ?? 0))});
    }
    if (method === 'setMyCommands') {
      if (!Array.isArray(body.commands) || !body.commands.every(c => typeof c.command === 'string' && typeof c.description === 'string')) return answer(400, {ok: false, description: 'Invalid commands'});
      return answer(200, {ok: true, result: true});
    }
    if (method === 'sendMessage') {
      if (String(body.chat_id) !== '12345' || typeof body.text !== 'string') return answer(400, {ok: false, description: 'chat_id and text required'});
      if (body.text.includes('FAIL_TELEGRAM')) return answer(503, {ok: false, description: 'Injected upstream failure'});
      return answer(200, {ok: true, result: {message_id: 2, date: 1794513600, chat: {id: 12345, type: 'private'}, text: body.text}});
    }
    return answer(501, {ok: false, description: 'Outside the local contract subset'});
  };
  if (req.body !== undefined) return handle(req.body);
  let raw = '';req.on('data', chunk => raw += chunk);req.on('end', () => {try {handle(JSON.parse(raw));} catch {answer(400, {ok: false, description: 'Invalid JSON'});}});
});
server.listen(process.env.PORT || 4011);
