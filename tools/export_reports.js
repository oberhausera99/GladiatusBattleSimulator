/*
 * Turma jelentések exportálása a SAJÁT, bejelentkezett böngésződből.
 *
 * Használat:
 *  1. Nyisd meg a játékot bejelentkezve (pl. a Circus Turma jelentéslistát).
 *  2. F12 -> Console, illeszd be ezt a fájlt, majd futtasd:
 *       await exportTurmaReports({ fromPage: 1, toPage: 5 })      // kb. 5 oldal
 *     (a lista ~10 jelentés/oldal; kezdd kicsiben, pl. 1-5 oldal)
 *  3. 50 jelentésenként letölt egy turma_reports_N.json fájlt (nyers HTML-lel).
 *     Ezeket told fel a repo `samples/` mappájába.
 *
 * A szkript lassan kér (alapból 1,2 mp/kérés), ugyanúgy mint egy kézi böngészés.
 * Az `sh=` munkamenet-token az URL-ből jön, a fájlokba NEM kerül bele.
 */
async function exportTurmaReports({ fromPage = 1, toPage = 1, delayMs = 1200, chunk = 50 } = {}) {
  const sh = new URL(location.href).searchParams.get('sh');
  if (!sh) throw new Error('Nincs sh= az aktuális URL-ben; nyiss meg egy játékoldalt.');
  const base = location.origin + '/game/index.php';
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const get = async url => {
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) throw new Error(r.status + ' ' + url);
    return r.text();
  };
  const download = (name, data) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
    a.download = name; a.click();
  };

  const ids = [];
  for (let p = fromPage; p <= toPage; p++) {
    const html = await get(`${base}?mod=reports&submod=showCircusTurma&page=${p}&sh=${sh}`);
    const found = [...html.matchAll(/showCombatReport[^"']*?reportId=(\d+)/g)].map(m => m[1]);
    for (const id of found) if (!ids.includes(id)) ids.push(id);
    console.log(`lista ${p}/${toPage}: ${ids.length} jelentés eddig`);
    await sleep(delayMs);
  }

  let buf = [], part = 1;
  for (let i = 0; i < ids.length; i++) {
    try {
      const html = await get(`${base}?mod=reports&submod=showCombatReport&t=3&reportId=${ids[i]}&sh=${sh}`);
      buf.push({ reportId: ids[i], html: html.replace(/sh=[0-9a-f]{32}/g, 'sh=X') });
    } catch (e) { console.warn('hiba', ids[i], e.message); }
    console.log(`jelentés ${i + 1}/${ids.length}`);
    if (buf.length >= chunk || i === ids.length - 1) {
      if (buf.length) download(`turma_reports_${part++}.json`, buf);
      buf = [];
    }
    await sleep(delayMs);
  }
  console.log('Kész.');
}
