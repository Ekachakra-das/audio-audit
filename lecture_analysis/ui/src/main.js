import { mount } from 'svelte';
import './app.css'
import App from './App.svelte'

// Global Error Handler for "Blank Screen" debugging
window.onerror = function (msg, source, lineno, colno, error) {
  document.body.innerHTML = `
    <div style="padding: 20px; color: red; font-family: monospace; background: #fff0f0;">
      <h1>Startup Error</h1>
      <p><strong>Message:</strong> ${msg}</p>
      <p><strong>Location:</strong> ${source}:${lineno}</p>
      <pre style="background: #eee; padding: 10px;">${error ? error.stack : 'No stack trace'}</pre>
    </div>
  `;
};

try {
  const target = document.getElementById('app');
  if (!target) throw new Error("Could not find #app element in DOM");

  // Svelte 5 API
  mount(App, {
    target: target,
  });

} catch (e) {
  window.onerror(e.message, 'main.js', 0, 0, e);
}
