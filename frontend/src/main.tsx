import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './lib/i18n'; // Initialize i18n translation engine
import './index.css';
import App from './App.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
