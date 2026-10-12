// The browser app's entry point.
import { render } from 'preact';
import { html } from './html.js';

function App() {
  return html`
    <main class="boot">
      <h1>MoneyKata</h1>
    </main>
  `;
}

const root = document.getElementById('app');
if (root) render(html`<${App} />`, root);
