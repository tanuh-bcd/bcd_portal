import React from 'react';
import ReactDOM from 'react-dom/client';
import mixpanel from 'mixpanel-browser';
import App from './App';
import './index.css';
import './i18n';
import * as serviceWorkerRegistration from './serviceWorkerRegistration';

const MIXPANEL_TOKEN = process.env.REACT_APP_MIXPANEL_TOKEN;
if (MIXPANEL_TOKEN) {
  mixpanel.init(MIXPANEL_TOKEN, { track_pageview: true, persistence: 'localStorage' });
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <App />
);

if (process.env.NODE_ENV === 'production') {
  serviceWorkerRegistration.register({
    onUpdate: (registration) => {
      if (registration.waiting) {
        registration.waiting.addEventListener('statechange', (e) => {
          if (e.target.state === 'activated') window.location.reload();
        });
      }
    },
  });
} else {
  // Prevent an older production bundle from controlling localhost during development.
  serviceWorkerRegistration.unregister();
}
