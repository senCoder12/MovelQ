const crypto = require('node:crypto');
if (!crypto.getRandomValues && crypto.webcrypto) {
  crypto.getRandomValues = function(arr) {
    return crypto.webcrypto.getRandomValues(arr);
  };
}
if (typeof globalThis.crypto === 'undefined' && crypto.webcrypto) {
  globalThis.crypto = crypto.webcrypto;
}
