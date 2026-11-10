// ERGASTERION: loads the 3D floor on its own, so a missing three.js or WebGL never stops the page (ergasterion.js waits for the event, then keeps the flat plan view).
import * as T from './floor.js';
window.__ergFloor = T;
window.dispatchEvent(new Event('erg-floor'));
