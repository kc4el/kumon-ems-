/* Employee documents: show stored records, never imply verification. */
(() => {
  const list = document.getElementById('profileDocuments');
  const context = document.getElementById('walkthroughContext');
  if (!list || !context?.dataset.employee) return;
  let loading = false;
  const names = {NBI:'NBI Clearance', BIR2316:'BIR Form 2316', PSA:'PSA Birth Certificate', contract:'Signed Employment Contract', government_records:'Government Records'};
  const text = message => { list.textContent = message; };
  async function load() {
    if (loading) return; loading = true; text('Loading documents...');
    try {
      const rows = []; let url = '/api/onboarding-docs/?employee=' + encodeURIComponent(context.dataset.employee);
      while (url) {
        const parsed = new URL(url, location.origin);
        if (parsed.origin !== location.origin || !parsed.pathname.startsWith('/api/')) throw new Error('Invalid page link.');
        const response = await portalFetch(parsed.pathname + parsed.search);
        if (!response.ok) throw new Error('Documents could not be loaded.');
        const data = await response.json(); rows.push(...(Array.isArray(data) ? data : data.results || [])); url = Array.isArray(data) ? null : data.next;
      }
      list.replaceChildren();
      if (!rows.length) { text('No documents are on file for your employee record. Contact HR if a required document is missing.'); return; }
      rows.forEach(row => {
        const item = document.createElement('div'); item.className = 'doc-list-item';
        const label = document.createElement('span'); label.textContent = names[row.doc_type] || row.doc_type || 'Document'; item.append(label);
        const link = document.createElement('a'); link.textContent = 'Download';
        // Use the canonical authenticated route, rather than a raw media URL.
        link.href = '/api/onboarding-docs/' + encodeURIComponent(row.id) + '/download/'; item.append(link); list.append(item);
      });
    } catch (error) { text(error.message || 'Documents could not be loaded.'); } finally { loading = false; }
  }
  document.getElementById('refreshProfileDocuments')?.addEventListener('click', load);
  const panel = document.getElementById('profilePanel');
  new MutationObserver(() => { if (panel.classList.contains('active')) load(); }).observe(panel, {attributes:true, attributeFilter:['class']});
  if (panel.classList.contains('active')) load();
})();
