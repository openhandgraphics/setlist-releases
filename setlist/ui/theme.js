/* A local, explicit preference. Light remains the default. */
(()=>{
 let theme='light';try{if(localStorage.getItem('setlist-theme')==='dark')theme='dark'}catch{}
 document.documentElement.dataset.theme=theme;
 document.addEventListener('DOMContentLoaded',()=>{
  const button=document.getElementById('themeToggle');
  function render(){button.textContent=theme==='dark'?'Light':'Dark';button.setAttribute('aria-label','Use '+(theme==='dark'?'light':'dark')+' theme');button.setAttribute('aria-pressed',String(theme==='dark'));document.documentElement.dataset.theme=theme}
  button.onclick=()=>{theme=theme==='dark'?'light':'dark';try{localStorage.setItem('setlist-theme',theme)}catch{}render()};
  render();
 });
})();
