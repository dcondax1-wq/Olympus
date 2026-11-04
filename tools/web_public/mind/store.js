// OLYMPUS Mind: this page's own small memory (this phone only): the theme, the toggles, the vault name, the review cards.
// Every key starts with 'mind.'; nothing else is ever touched here. A blocked or full storage never breaks the page (it just forgets).
//   load(name, fallback) -> the saved JSON value (or the fallback)     save(name, value) -> true when kept
const P = 'mind.';

export function load(name, fallback) {
  try {
    const v = localStorage.getItem(P + name);
    return v == null ? fallback : JSON.parse(v);
  } catch (_) {
    return fallback;
  }
}

export function save(name, value) {
  try {
    localStorage.setItem(P + name, JSON.stringify(value));
    return true;
  } catch (_) {
    return false;                                   // private mode or full: this visit only
  }
}
