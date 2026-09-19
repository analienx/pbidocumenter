#!/usr/bin/env node
/** Opt-in, no-tools Pi RPC transport for source-bound image review. */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';

const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const provider = spec.provider;
if (!['cline', 'cline-pass'].includes(provider)) throw Error('Unsupported Pi review provider');
if (!spec.model?.startsWith(provider + '/') || !spec.model.includes('/')) throw Error('Invalid model');
const agentDir = path.resolve(spec.agent_dir || path.join(os.homedir(), '.pi', 'agent'));
const extension = path.join(agentDir, 'npm', 'node_modules', '@maxpaulus', 'pi-cline', 'index.ts');
if (!fs.existsSync(extension)) throw Error('Pi Cline provider is not installed in the selected profile');
const cli = process.platform === 'win32'
  ? path.join(process.env.APPDATA, 'npm', 'node_modules', '@earendil-works', 'pi-coding-agent', 'dist', 'bundle', 'cli.js')
  : spec.pi_cli;
if (!cli || !fs.existsSync(cli)) throw Error('Pi CLI is unavailable');
const textPlanner = spec.task === 'repair_planning';
if (!Array.isArray(spec.images) || (textPlanner ? spec.images.length !== 0 : spec.images.length < 1 || spec.images.length > 6)) throw Error('Image review requires 1..6 images; text repair planning requires zero images');
const images = spec.images.map(item => {
  const file = path.resolve(item.path);
  const data = fs.readFileSync(file);
  if (data.length > 12000000 || data.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw Error('Invalid/oversized PNG');
  if (crypto.createHash('sha256').update(data).digest('hex') !== item.sha256) throw Error('Image digest mismatch');
  return { type: 'image', data: data.toString('base64'), mimeType: 'image/png' };
});
const args = [cli, '--mode', 'rpc', '--no-session', '--no-tools', '--no-skills',
  '--no-prompt-templates', '--no-context-files', '--no-extensions', '-e', extension,
  '--provider', provider, '--model', spec.model, '--thinking', spec.thinking || 'off'];
const env = { ...process.env, PI_CODING_AGENT_DIR: agentDir };
delete env.CLINE_API_KEY; delete env.CLINEPASS_API_KEY;
const child = spawn(process.execPath, args, { cwd: os.tmpdir(), env,
  stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
let finished = false, pending = '', stage = 'state';
const deadline = Math.min(600000, Math.max(30000, Number(spec.timeout_seconds || 180) * 1000));
const timer = setTimeout(() => finish('timeout'), deadline);
function finish(error, content = '') {
  if (finished) return;
  finished = true; clearTimeout(timer);
  process.stdout.write(JSON.stringify({ ok: !error, model: spec.model,
    image_count: images.length, content, error: error || null }) + '\n');
  child.stdin.end();
  setTimeout(() => { if (child.exitCode === null) child.kill(); }, 1200).unref();
  process.exitCode = error ? 2 : 0;
}
child.stdin.write(JSON.stringify({ id: 'capability', type: 'get_state' }) + '\n');
child.stdout.on('data', chunk => {
  pending += chunk.toString(); let end;
  while ((end = pending.indexOf('\n')) >= 0) {
    const line = pending.slice(0, end).trim(); pending = pending.slice(end + 1);
    if (!line) continue;
    let event; try { event = JSON.parse(line); } catch { continue; }
    if (event.type === 'response' && event.command === 'get_state') {
      const model = event.data?.model;
      if (!event.success || !model || (!textPlanner && !model.input?.includes('image'))) {
        finish('selected_model_does_not_accept_required_input'); continue;
      }
      if (model.provider !== provider || ![spec.model, spec.model.slice(provider.length + 1)].includes(model.id)) {
        finish('selected_model_identity_mismatch'); continue;
      }
      if (!finished && stage === 'state') {
        stage = 'prompt';
        child.stdin.write(JSON.stringify({ id: 'visual-review', type: 'prompt',
          message: spec.prompt, images }) + '\n');
      }
    }
    if (event.type === 'response' && event.success === false) finish('pi_rpc_command_rejected');
    if (event.type === 'message_end' && event.message?.role === 'assistant' && stage === 'prompt') {
      const msg = event.message;
      if (msg.stopReason === 'error' || msg.errorMessage) finish('model_response_error');
      else finish(null, (msg.content || []).filter(item => item?.type === 'text')
        .map(item => item.text).join(''));
    }
  }
});
child.stderr.on('data', () => {}); // Never echo provider logs, tokens, or image data.
child.on('error', () => finish('pi_spawn_failed'));
child.on('exit', code => { if (!finished) finish('pi_terminated_' + code); });
