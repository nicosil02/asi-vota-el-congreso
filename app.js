// Así vota el Congreso: interacción de todas las páginas. Sin dependencias.
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const quieto = matchMedia('(prefers-reduced-motion: reduce)').matches;
const plano = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// Pestañas
$$('.pestanas').forEach((lista) => {
  const tabs = $$('[role=tab]', lista);
  const elegir = (t) => tabs.forEach((x) => {
    const si = x === t;
    x.setAttribute('aria-selected', si);
    x.tabIndex = si ? 0 : -1;
    document.getElementById(x.getAttribute('aria-controls')).hidden = !si;
  });
  tabs.forEach((t, i) => {
    t.tabIndex = i ? -1 : 0;
    t.onclick = () => elegir(t);
    t.onkeydown = (ev) => {
      const d = ev.key === 'ArrowRight' ? 1 : ev.key === 'ArrowLeft' ? -1 : 0;
      if (d) { const n = tabs[(i + d + tabs.length) % tabs.length]; elegir(n); n.focus(); }
    };
  });
});

// "Leer más"
$$('[data-abre]').forEach((b) => b.onclick = () => {
  const p = document.getElementById(b.dataset.abre), abierto = p.classList.toggle('abierto');
  b.textContent = abierto ? 'Leer menos' : 'Leer más';
});

// Listas filtrables: buscador, chips y "mostrar trámites"
$$('.filtrable').forEach((caja) => {
  const filas = $$('.fila, tbody tr', caja), q = $('.buscar', caja), tram = $('.ver-tramites', caja);
  const cuenta = $('.cuenta', caja), vacio = $('.vacio', caja), contiene = caja.dataset.modo === 'contiene';
  const sel = {};
  const pinta = () => {
    const s = plano(q?.value.trim());
    let n = 0;
    filas.forEach((f) => {
      const ok = (!s || plano(f.dataset.q).includes(s))
        && (!sel.v || (contiene ? (f.dataset.v || '').split(' ').includes(sel.v) : f.dataset.v === sel.v))
        && (!sel.camara || f.dataset.camara === sel.camara)
        && (!('tramite' in f.dataset) || tram?.checked);
      f.hidden = !ok; n += ok;
    });
    if (cuenta) cuenta.textContent = `${n} de ${cuenta.dataset.total || filas.filter((f) => !('tramite' in f.dataset)).length} ${cuenta.dataset.quien || ''}`;
    if (vacio) vacio.hidden = n > 0;
  };
  $$('.chips', caja).forEach((g) => $$('button', g).forEach((b) => b.onclick = () => {
    sel[g.dataset.grupo] = b.dataset.v;
    $$('button', g).forEach((x) => x.setAttribute('aria-pressed', x === b));
    pinta();
  }));
  if (q) q.oninput = pinta;
  if (tram) tram.onchange = pinta;
  pinta();
});

// Carrusel de la portada: avanza solo cada 5,5 s
const carr = $('.carrusel');
if (carr) {
  const laminas = $$('.lamina', carr), barras = $$('.barras .b', carr), pista = $('.pista', carr);
  let i = 0, reloj;
  const ir = (k) => {
    i = (k + laminas.length) % laminas.length;
    pista.style.transform = `translateX(${-i * 100}%)`;
    laminas.forEach((l, n) => { l.classList.remove('vivo'); l.setAttribute('aria-hidden', n !== i); l.tabIndex = n === i ? 0 : -1; });
    barras.forEach((b) => b.classList.remove('ahora'));
    void carr.offsetWidth;  // reinicia las animaciones
    laminas[i].classList.add('vivo');
    barras.forEach((b, n) => { b.classList.toggle('llena', n < i); if (n === i) b.classList.add('ahora'); });
  };
  const arranca = () => { clearInterval(reloj); if (!quieto) reloj = setInterval(() => ir(i + 1), 5500); };
  $('.adelante', carr).onclick = () => { ir(i + 1); arranca(); };
  $('.atras', carr).onclick = () => { ir(i - 1); arranca(); };
  barras.forEach((b, n) => b.onclick = () => { ir(n); arranca(); });
  carr.onkeydown = (ev) => { if (ev.key === 'ArrowRight') { ir(i + 1); arranca(); } if (ev.key === 'ArrowLeft') { ir(i - 1); arranca(); } };
  // deslizar con el dedo
  let x0 = null, y0 = 0;
  carr.addEventListener('touchstart', (ev) => { x0 = ev.touches[0].clientX; y0 = ev.touches[0].clientY; clearInterval(reloj); }, { passive: true });
  carr.addEventListener('touchend', (ev) => {
    if (x0 === null) return;
    const dx = ev.changedTouches[0].clientX - x0, dy = ev.changedTouches[0].clientY - y0;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) { ir(i + (dx < 0 ? 1 : -1)); ev.preventDefault(); }
    x0 = null; arranca();
  });
  carr.addEventListener('focusin', () => clearInterval(reloj));
  carr.addEventListener('focusout', arranca);
  ir(0); arranca();
}

// Iniciativas: buscador sobre todas, con ficha al tocar una
const raiz = $('#iniciativas');
if (raiz) {
  const LOGO = { FP: 'fuerza-popular.svg', JP: 'juntos-por-el-peru.svg', RP: 'renovacion-popular.png', AN: 'ahora-nacion.jpg',
                 PBG: 'partido-del-buen-gobierno.jpg', PCO: 'partido-civico-obras.png' };
  const EST = { pres: ['Presentada', '#4F5B6B'], com: ['En comisión', '#2C5AA0'], dict: ['Con dictamen', '#8C6D0E'], pleno: ['En el pleno', '#8C6D0E'],
                sen: ['Pasó al Senado', '#2C5AA0'], apr: ['Aprobada', '#1E8A4C'], ley: ['Publicada', '#14663A'], ret: ['Retirada', '#6B7685'], arch: ['Archivada', '#6B7685'] };
  const CAM = { D: 'Diputados', S: 'Senado', C: 'Congreso' };
  const punto = (e) => `<span class="estado" style="color:${EST[e][1]}"><i style="background:${EST[e][1]}"></i>${EST[e][0]}</span>`;
  const f = { q: '', tema: '', cam: '', quien: '', estado: '' };
  let todas = [], tope = 50, fichas, orden = [9, -1];
  const ORDEN_EST = ['pres', 'com', 'dict', 'pleno', 'sen', 'apr', 'ley', 'ret', 'arch'];
  const lista = $('#lista-i'), mas = $('.mas', raiz), cuenta = $('.cuenta', raiz);

  const pinta = () => {
    const s = plano(f.q.trim());
    const ok = todas.filter(([k, num, cam, fe, e, tema, sig, quien, t]) =>
      (!s || plano(t).includes(s) || String(num) === s) && (!f.tema || tema === f.tema) && (!f.cam || cam === f.cam)
      && (!f.quien || quien === f.quien) && (!f.estado || e === f.estado || (f.estado === 'fin' && (e === 'ret' || e === 'arch'))));
    cuenta.textContent = `${ok.length.toLocaleString('es-PE')} ${ok.length === 1 ? 'iniciativa' : 'iniciativas'}`;
    const [col, dir] = orden;
    const val = (x) => col === 4 ? ORDEN_EST.indexOf(x[4]) : x[col];
    ok.sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * dir || (b[9] > a[9] ? 1 : -1));
    lista.innerHTML = ok.length ? ok.slice(0, tope).map(([k, num, cam, fe, e, tema, sig, quien, t, iso, com]) => `
      <tr data-k="${k}" tabindex="0"><td class="f">${fe}</td><td class="n">${num}</td><td class="c-cam">${CAM[cam]}</td>
      <td class="t"><span>${esc(t)}</span></td><td>${punto(e)}</td>
      <td class="c-ext">${sig ? `<img class="mini" src="logos/${LOGO[sig]}" alt="">` : ''}${esc(quien)}</td><td class="c-ext">${esc(com)}</td><td class="c-ext">${esc(tema)}</td></tr>`).join('')
      : '<tr><td colspan="8" class="nota">Ninguna iniciativa con estos filtros. Prueba con otra palabra o quita un filtro.</td></tr>';
    mas.hidden = ok.length <= tope;
  };

  const hoja = $('.hoja'), velo = $('.velo');
  let antes;
  const cierra = () => {
    hoja.hidden = velo.hidden = true;
    $$('tr[aria-selected]', lista).forEach((r) => r.removeAttribute('aria-selected'));
    document.body.style.overflow = '';
    history.replaceState(null, '', location.pathname + location.search);
    antes?.focus();
  };
  const abre = async (k) => {
    const i = todas.find((x) => x[0] === k);
    if (!i) return;
    const [, num, cam, fe, e, tema, sig, quien, t] = i;
    antes = document.activeElement;
    $('#h-meta').textContent = `${CAM[cam]}, n.º ${num}`;
    $('#h-titulo').textContent = t;
    $('#h-estado').innerHTML = punto(e);
    $('#h-cuerpo').innerHTML = '<p class="nota">Cargando…</p>';
    hoja.hidden = velo.hidden = false;
    document.body.style.overflow = 'hidden';
    hoja.focus();
    history.replaceState(null, '', '#' + k);
    $$('tr[data-k]', lista).forEach((r) => r.setAttribute('aria-selected', r.dataset.k === k));
    fichas = fichas || new Promise((ok, mal) => {  // se carga al abrir la primera ficha
      const s = document.createElement('script');
      s.src = 'datos/fichas.js?v=' + Date.now().toString().slice(0, 7); s.onload = () => ok(window.FICHAS); s.onerror = mal;
      document.head.append(s);
    });
    const x = (await fichas)[k];
    if (hoja.hidden) return;
    const ult = x.tram.length - 1;
    const dato = (a, b) => b ? `<dt>${a}</dt><dd>${esc(b)}</dd>` : '';
    $('#h-cuerpo').innerHTML = `<dl>${dato('Comisión', x.com)}${dato('Presentada', fe)}${dato(sig ? 'Bancada' : 'Presentada por', quien)}${dato('Autores', x.aut)}${dato('Tema', tema)}</dl>
      <h3>Trámite y documentos</h3>
      <ol class="tramite">${x.tram.map((p, n) => `<li><span class="num" style="background:${n === ult ? EST[e][1] : '#8994A3'}">${n + 1}</span><div><b>${esc(p.p)}</b><span class="meta">${p.f}</span>
        ${p.d.map((d) => `<a class="pdf" href="${esc(d.u)}" target="_blank" rel="noopener"><span>PDF</span>${esc(d.n)}</a>`).join('')}</div></li>`).join('')}</ol>
      ${x.url ? `<a class="boton" href="${esc(x.url)}" target="_blank" rel="noopener">Ver en el portal del Congreso</a>` : ''}`;
  };

  lista.onclick = (ev) => { const b = ev.target.closest('[data-k]'); if (b) abre(b.dataset.k); };
  lista.onkeydown = (ev) => { const b = ev.target.closest('[data-k]'); if (b && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); abre(b.dataset.k); } };
  $$('th[data-o]', raiz).forEach((th) => th.querySelector('button').onclick = () => {
    const c = +th.dataset.o;
    orden = [c, orden[0] === c ? -orden[1] : (c === 9 ? -1 : 1)];
    $$('th[data-o]', raiz).forEach((x) => x.removeAttribute('aria-sort'));
    th.setAttribute('aria-sort', orden[1] > 0 ? 'ascending' : 'descending');
    pinta();
  });
  $('.cerrar', hoja).onclick = cierra;
  velo.onclick = cierra;
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !hoja.hidden) cierra(); });
  mas.onclick = () => { tope += 50; pinta(); };
  $('#qi').oninput = (ev) => { f.q = ev.target.value; tope = 50; pinta(); };
  $$('select[data-f]', raiz).forEach((s) => s.onchange = () => { f[s.dataset.f] = s.value; tope = 50; pinta(); });
  $$('.chips button', raiz).forEach((b) => b.onclick = () => {
    f.estado = b.dataset.v; tope = 50;
    $$('.chips button', raiz).forEach((x) => x.setAttribute('aria-pressed', x === b));
    pinta();
  });

  todas = window.INICIATIVAS || [];
  pinta();
  const desdeHash = () => { if (location.hash.length > 1) abre(decodeURIComponent(location.hash.slice(1))); };
  addEventListener('hashchange', desdeHash);
  desdeHash();
}
