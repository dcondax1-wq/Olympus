// SYMPOSIUM: loads the 3D hall on its own, so a missing three.js or WebGL never stops the page (symposium.js waits for the event, then keeps the portrait grid).
import * as T from './hall.js';
window.__symHall = T;
window.dispatchEvent(new Event('sym-hall'));
