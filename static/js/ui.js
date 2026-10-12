/* Progressive enhancement: all navigation/forms use the Flask routes. */
(() => {
  'use strict';
  document.documentElement.classList.add('js');
  document.querySelectorAll('[data-enhanced]').forEach(el => { el.hidden = false; });
  const menuButton = document.querySelector('.sc-menu-toggle');
  const menu = document.getElementById('sc-menu');
  menuButton?.addEventListener('click', () => {
    const expanded = menuButton.getAttribute('aria-expanded') !== 'true';
    menuButton.setAttribute('aria-expanded', String(expanded));
    menu?.classList.toggle('is-open', expanded);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu?.classList.contains('is-open')) {
      menu.classList.remove('is-open'); menuButton.setAttribute('aria-expanded', 'false'); menuButton.focus();
    }
  });
  document.querySelectorAll('.sc-dismiss').forEach(button => button.addEventListener('click', () => button.closest('.sc-flash').remove()));
  document.querySelectorAll('[data-poster]').forEach(img => {
    const hideFailed = () => { img.hidden = true; };
    img.addEventListener('error', hideFailed);
    if (img.complete && img.naturalWidth === 0) hideFailed();
  });

  // Catalogue search, language filter and stable sorting affect only catalogue cards.
  document.querySelectorAll('[data-catalogue]').forEach(catalogue => {
    const grid = catalogue.querySelector('[data-movie-grid]');
    if (!grid) return;
    const cards = [...grid.querySelectorAll('[data-movie-card]')];
    const search = catalogue.querySelector('[data-movie-search]');
    const language = catalogue.querySelector('[data-movie-language]');
    const sort = catalogue.querySelector('[data-movie-sort]');
    const update = () => {
      const query = search.value.trim().toLocaleLowerCase();
      cards.forEach(card => { card.hidden = !card.dataset.title.toLocaleLowerCase().includes(query) || !!language.value && card.dataset.language !== language.value; });
      [...cards].sort((a, b) => sort.value === 'rating'
        ? Number(b.dataset.rating) - Number(a.dataset.rating) || a.dataset.title.localeCompare(b.dataset.title)
        : a.dataset.title.localeCompare(b.dataset.title)).forEach(card => grid.appendChild(card));
      const count = cards.filter(card => !card.hidden).length;
      catalogue.querySelector('[data-result-count]').textContent = `${count} ${count === 1 ? 'movie' : 'movies'}`;
      catalogue.querySelector('[data-filter-empty]').hidden = count !== 0;
    };
    search.addEventListener('input', update); language.addEventListener('change', update); sort.addEventListener('change', update);
    catalogue.querySelectorAll('[data-filter-reset]').forEach(button => button.addEventListener('click', () => {
      search.value = ''; language.value = ''; sort.value = 'title'; update(); search.focus();
    }));
    update();
  });

  document.querySelectorAll('[data-show-browser]').forEach(browser => {
    const date = browser.querySelector('[data-show-date]');
    const theatre = browser.querySelector('[data-show-theatre]');
    if (!date || !theatre) return;
    const cards = [...browser.querySelectorAll('[data-show-card]')];
    const update = () => {
      cards.forEach(card => { card.hidden = !!date.value && card.dataset.date !== date.value || !!theatre.value && card.dataset.theatre !== theatre.value; });
      const count = cards.filter(card => !card.hidden).length;
      browser.querySelector('[data-show-count]').textContent = `${count} ${count === 1 ? 'show' : 'shows'}`;
      browser.querySelector('[data-show-empty]').hidden = count !== 0;
    };
    date.addEventListener('change', update); theatre.addEventListener('change', update);
  });

  const picker = document.querySelector('[data-seat-picker]');
  if (picker) {
    const price = Number(picker.dataset.price);
    const chosen = new Map();
    const seats = [...picker.querySelectorAll('.seat:not(:disabled)')];
    const form = document.getElementById('bookingForm');
    const submit = document.getElementById('bookButton');
    const clear = picker.querySelector('[data-clear-seats]');
    const summary = () => {
      document.getElementById('selectedSeatsInput').value = [...chosen.keys()].join(',');
      document.getElementById('selectedSeatCount').textContent = String(chosen.size);
      document.getElementById('selectedSeatNumbers').textContent = chosen.size ? [...chosen.values()].join(', ') : 'No seats selected';
      document.getElementById('totalAmount').textContent = '₹' + (chosen.size * price).toFixed(2);
      submit.disabled = chosen.size === 0 || !Number.isFinite(price);
      submit.textContent = chosen.size ? `Reserve ${chosen.size} ${chosen.size === 1 ? 'seat' : 'seats'} →` : 'Select seats to continue';
      clear.disabled = chosen.size === 0;
    };
    seats.forEach(seat => seat.addEventListener('click', () => {
      if (chosen.has(seat.dataset.seatId)) chosen.delete(seat.dataset.seatId);
      else chosen.set(seat.dataset.seatId, seat.dataset.seatNumber);
      const selected = chosen.has(seat.dataset.seatId);
      seat.classList.toggle('seat-selected', selected); seat.classList.toggle('seat-available', !selected);
      seat.setAttribute('aria-pressed', String(selected)); summary();
    }));
    clear.addEventListener('click', () => {
      chosen.clear(); seats.forEach(seat => { seat.classList.remove('seat-selected'); seat.classList.add('seat-available'); seat.setAttribute('aria-pressed', 'false'); }); summary();
    });
    form.addEventListener('submit', event => { if (chosen.size === 0 || !Number.isFinite(price)) event.preventDefault(); });
    summary();
  }

  // Preserve existing form names and values, and add accessible password visibility.
  document.querySelectorAll('input[type="password"]').forEach((input, index) => {
    if (!input.id) input.id = `sc-password-${index}`;
    input.autocomplete = location.pathname.includes('register') ? 'new-password' : 'current-password';
    const wrap = document.createElement('div'); wrap.className = 'sc-password-wrap';
    input.parentNode.insertBefore(wrap, input); wrap.appendChild(input);
    const toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'sc-password-toggle'; toggle.textContent = 'Show';
    toggle.setAttribute('aria-controls', input.id); toggle.setAttribute('aria-pressed', 'false'); toggle.setAttribute('aria-label', 'Show password');
    toggle.addEventListener('click', () => {
      const visible = input.type === 'password'; input.type = visible ? 'text' : 'password';
      toggle.textContent = visible ? 'Hide' : 'Show'; toggle.setAttribute('aria-pressed', String(visible)); toggle.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
    });
    wrap.appendChild(toggle);
  });
  document.querySelectorAll('input[type="email"]').forEach(input => { input.autocomplete = 'email'; });
  // Star shortcuts update the original select used by Flask validation.
  document.querySelectorAll('select[name="rating"]').forEach(select => {
    const group = document.createElement('div'); group.className = 'sc-rating-controls'; group.setAttribute('role', 'group'); group.setAttribute('aria-label', 'Choose rating');
    const buttons = [];
    for (let value = 1; value <= 5; value++) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'sc-rating-button'; button.textContent = `${value} ★`; button.setAttribute('aria-label', `Rate ${value} out of 5`);
      button.addEventListener('click', () => { select.value = String(value); select.dispatchEvent(new Event('change', { bubbles: true })); });
      group.appendChild(button); buttons.push(button);
    }
    const sync = () => buttons.forEach((button, index) => button.setAttribute('aria-pressed', String(Number(select.value) === index + 1)));
    select.addEventListener('change', sync); select.insertAdjacentElement('afterend', group); sync();
  });
  // Filter existing admin tables without changing database queries or form actions.
  if (location.pathname.startsWith('/admin/')) document.querySelectorAll('.table-responsive').forEach((wrapper, index) => {
    const table = wrapper.querySelector('table'); if (!table?.tBodies.length || table.tBodies[0].rows.length < 2) return;
    const field = document.createElement('div'); field.className = 'sc-table-filter';
    const label = document.createElement('label'); label.htmlFor = `table-search-${index}`; label.textContent = 'Search this table';
    const input = document.createElement('input'); input.type = 'search'; input.id = label.htmlFor; input.className = 'form-control'; input.placeholder = 'Type to filter…';
    const count = document.createElement('span'); count.className = 'sc-meta'; count.setAttribute('aria-live', 'polite');
    const rows = [...table.tBodies[0].rows];
    input.addEventListener('input', () => {
      const query = input.value.trim().toLocaleLowerCase(); rows.forEach(row => { row.hidden = !row.textContent.toLocaleLowerCase().includes(query); });
      count.textContent = `${rows.filter(row => !row.hidden).length} of ${rows.length} rows`;
    });
    field.append(label, input, count); wrapper.before(field);
  });
  document.querySelectorAll('[data-print-ticket]').forEach(button => button.addEventListener('click', () => window.print()));
})();
