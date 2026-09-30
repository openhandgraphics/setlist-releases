(() => {
  const url = 'https://setlist-dj-zapata-lbk.openhandgraphics.chatgpt.site/';
  const button = document.getElementById('shareSite');
  const dialog = document.getElementById('shareDialog');
  const field = document.getElementById('shareUrl');
  const status = document.getElementById('shareCopyStatus');
  const feedback = document.getElementById('shareFeedback');
  let timer;
  const copied = () => {
    feedback.textContent = 'Link copied — ready to share.';
    feedback.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(() => { feedback.hidden = true; }, 4500);
  };
  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      copied();
      return true;
    } catch { return false; }
  }
  button.addEventListener('click', async () => {
    if (navigator.share) {
      try {
        await navigator.share({title: 'Setlist — Your next great setlist', text: 'Build DJ playlists from your own music library. Try Setlist for Windows.', url});
        return;
      } catch (error) {
        if (error.name === 'AbortError') return;
      }
    }
    if (await copy()) return;
    status.textContent = '';
    dialog.showModal();
    field.focus();
    field.select();
  });
  document.getElementById('copyShareLink').addEventListener('click', async () => {
    if (await copy()) { dialog.close(); return; }
    field.focus();
    field.select();
    status.textContent = 'Select and copy the link above using your device’s copy command.';
  });
  document.getElementById('closeShareDialog').addEventListener('click', () => dialog.close());
})();
