(() => {
  const form = document.getElementById('frm_ctrl');
  if (!(form instanceof HTMLFormElement)) return;

  const setField = (id, value) => {
    const el = document.getElementById(id);
    if (el instanceof HTMLInputElement) el.value = String(value);
  };

  const getField = (id) => {
    const el = document.getElementById(id);
    return el instanceof HTMLInputElement ? el.value : '';
  };

  const postForm = (path, values) => {
    const body = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => body.set(key, String(value)));
    return fetch(path, { method: 'POST', body });
  };

  if ('%%PAGE%%' === 'menu') {
    const enter = document.getElementById('enter');
    const order = document.getElementById('order');
    const decide = document.getElementById('decide');
    const back = document.getElementById('back');
    const amountInput = document.getElementById('amount');
    const modAmountInput = document.getElementById('mod_amount');
    const orderTimeInput = document.getElementById('order-time');
    const mainName = document.querySelector('.detail .main .name dt');
    const mainPrice = document.querySelector('.detail .main .name dd');
    const modSection = document.querySelector('.detail .mod');
    const modName = document.querySelector('.detail .mod .name dt');
    const modPrice = document.querySelector('.detail .mod .name dd');
    const notice = document.querySelector('.notice-balloon .msg-base span');
    const guide = document.getElementById('guide');
    const guideText = guide ? guide.querySelector('.msg-base span') : null;
    let entered = '';
    let resolved = null;

    const setNotice = (text) => { if (notice) notice.textContent = text; };

    const renderEntered = () => {
      if (enter) enter.textContent = entered || ' ';
    };

    const resetDetail = () => {
      resolved = null;
      setField('code', '');
      setField('mod_code', '');
      if (mainName) mainName.textContent = ' ';
      if (mainPrice) mainPrice.textContent = '0円';
      if (modName) modName.textContent = ' ';
      if (modPrice) modPrice.textContent = '';
      if (modAmountInput instanceof HTMLInputElement) modAmountInput.value = '0';
      if (modSection instanceof HTMLElement) modSection.style.display = 'none';
      if (guide instanceof HTMLElement) guide.style.display = 'none';
    };

    const lookupItem = async () => {
      if (entered.length !== 4) {
        resetDetail();
        setNotice('メニューブックの番号を入力してください。');
        return;
      }
      try {
        const response = await postForm('./src/cmd/get_item.php', {
          sid: getField('shop-id'),
          tno: getField('table-no'),
          lng: 1,
          id: entered,
          num: getField('number') || 1,
          ssid: getField('session-id'),
        });
        const data = await response.json();
        if (data.result !== 'OK' || !data.item_data || data.item_data.state === 0) {
          resetDetail();
          setNotice('商品が見つかりません。');
          return;
        }
        resolved = data.item_data;
        setField('code', entered);
        if (mainName) mainName.textContent = data.item_data.name || ' ';
        if (mainPrice) mainPrice.textContent = String(data.item_data.price || 0) + '円';
        setNotice(data.item_data.notice || '商品を確認して確定してください。');
        if (data.item_data.mod_id) {
          setField('mod_code', data.item_data.mod_id);
          if (modName) modName.textContent = data.item_data.mod_name || ' ';
          if (modPrice) modPrice.textContent = data.item_data.mod_price
            ? String(data.item_data.mod_price) + '円'
            : '';
          if (modAmountInput instanceof HTMLInputElement) {
            modAmountInput.value = String(data.item_data.mod_ini_cnt || 0);
          }
          if (modSection instanceof HTMLElement) modSection.style.display = '';
          if (guide instanceof HTMLElement && guideText && data.item_data.mod_guid) {
            guide.style.display = '';
            guideText.textContent = data.item_data.mod_guid;
          }
        } else {
          setField('mod_code', '');
          if (modSection instanceof HTMLElement) modSection.style.display = 'none';
          if (guide instanceof HTMLElement) guide.style.display = 'none';
        }
      } catch {
        resetDetail();
        setNotice('商品の取得に失敗しました。');
      }
    };

    const adjustCount = (input, delta, minimum) => {
      if (!(input instanceof HTMLInputElement)) return;
      const current = Number.parseInt(input.value || String(minimum), 10);
      const next = Math.max(minimum, Math.min(99, current + delta));
      input.value = String(next);
    };

    const submitAdd = (event) => {
      if (event) event.preventDefault();
      if (!resolved || entered.length !== 4) {
        setNotice('4桁の商品番号を入力してください。');
        return;
      }
      setField('proc', 'main');
      setField('ctrl', 'add');
      if (orderTimeInput instanceof HTMLInputElement) {
        const now = new Date();
        const pad = (value) => String(value).padStart(2, '0');
        orderTimeInput.value =
          now.getFullYear() + '/' +
          pad(now.getMonth() + 1) + '/' +
          pad(now.getDate()) + ',' +
          pad(now.getHours()) + ':' +
          pad(now.getMinutes()) + ':' +
          pad(now.getSeconds());
      }
      form.requestSubmit();
    };

    renderEntered();
    resetDetail();
    document.querySelectorAll('.tenkey li[data-val]').forEach((key) => {
      key.addEventListener('click', async () => {
        if (entered.length >= 4) return;
        entered += key.getAttribute('data-val') || '';
        renderEntered();
        await lookupItem();
      });
    });
    document.querySelector('.tenkey .del')?.addEventListener('click', async () => {
      entered = entered.slice(0, -1);
      renderEntered();
      await lookupItem();
    });
    if (back) {
      back.addEventListener('click', (event) => {
        event.preventDefault();
        entered = '';
        renderEntered();
        if (amountInput instanceof HTMLInputElement) amountInput.value = '1';
        resetDetail();
        setNotice('メニューブックの番号を入力してください。');
      });
    }
    if (order) order.addEventListener('click', submitAdd);
    if (decide) decide.addEventListener('click', submitAdd);
    document.querySelector('.detail .main #minus')?.addEventListener('click', () => adjustCount(amountInput, -1, 1));
    document.querySelector('.detail .main #plus')?.addEventListener('click', () => adjustCount(amountInput, 1, 1));
    document.querySelector('.detail .mod #minus')?.addEventListener('click', () => adjustCount(modAmountInput, -1, 0));
    document.querySelector('.detail .mod #plus')?.addEventListener('click', () => adjustCount(modAmountInput, 1, 0));
  }

  if ('%%PAGE%%' === 'call') {
    const message = document.querySelector('#body-section .message');
    const callAfter = document.getElementById('call-after');
    const triggerCall = async (after) => {
      try {
        await postForm('./src/cmd/tbl_call.php', {
          sid: getField('shop-id'),
          tbl: getField('table-no'),
          aft: after,
        });
        if (message) {
          message.textContent = after
            ? 'デザート呼び出しを受け付けました。'
            : '店員呼び出しを受け付けました。';
        }
      } catch {
        if (message) message.textContent = '呼び出しに失敗しました。';
      }
    };
    document.getElementById('call-staff')?.addEventListener('click', () => { triggerCall(false); });
    callAfter?.addEventListener('click', () => {
      if (!callAfter.classList.contains('disabled')) triggerCall(true);
    });
  }
})();
