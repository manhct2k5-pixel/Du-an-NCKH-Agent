(() => {
  const form = document.getElementById('transaction-form');
  if (!form) return;
  const scenarios = window.__DEMO_SCENARIOS__ || [];
  const byId = id => document.getElementById(id);
  const submit = byId('submit-transaction');
  const reset = byId('reset-sample');
  const status = byId('form-status');
  const result = byId('result-shell');
  const empty = byId('result-empty');
  const labels = {approve:'Thông qua', review:'Cần xác minh', block:'Chặn', step_up:'Xác minh tăng cường'};
  const routes = {low:'Thấp', medium:'Trung bình', high:'Cao'};
  const tones = {approve:'success', review:'warning', block:'danger', step_up:'info', low:'success', medium:'warning', high:'danger'};
  let selected = scenarios[0];
  let pending = false;
  const text = (id, value) => { if (byId(id)) byId(id).textContent = value; };
  const number = (value, digits=3) => value != null && Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '—';
  const probability = value => value == null ? '—' : `${number(Number(value)*100, 4)}%`;
  function tone(node, value) {
    ['neutral','success','warning','danger','info'].forEach(name => node.classList.remove(`tone-${name}`));
    node.classList.add(`tone-${tones[value] || 'neutral'}`);
  }
  function setStatus(message, error=false) {
    status.textContent = message;
    status.classList.toggle('is-error', error);
  }
  function payload() {
    const data = new FormData(form);
    const p = {source:'paysim', tx_type:data.get('tx_type'), timestamp:data.get('timestamp'), extras:{}};
    ['amount','oldbalanceOrg','newbalanceOrig','oldbalanceDest','newbalanceDest'].forEach(name => { p[name] = Number(data.get(name)); });
    ['card_id','merchant_id','device_id','location_id','ip_address'].forEach(name => { p.extras[name] = data.get(name); });
    if (data.get('is_fraud') !== '') p.is_fraud = Number(data.get('is_fraud'));
    return p;
  }
  function preview() { text('payload-preview', JSON.stringify(payload(), null, 2)); }
  function clearErrors() {
    form.querySelectorAll('[aria-invalid]').forEach(node => { node.removeAttribute('aria-invalid'); node.removeAttribute('aria-describedby'); });
    form.querySelectorAll('.field-error').forEach(node => node.remove());
  }
  function fieldError(name, message) {
    const field = form.elements.namedItem(name);
    if (!field) return null;
    field.setAttribute('aria-invalid','true');
    const id = `${name}-error`;
    let note = byId(id);
    if (!note) { note = document.createElement('span'); note.id = id; note.className='field-error'; field.closest('label').append(note); }
    note.textContent = message;
    field.setAttribute('aria-describedby',id);
    return field;
  }
  function focusField(field) {
    for (let parent=field.parentElement; parent; parent=parent.parentElement) if (parent.tagName==='DETAILS') parent.open=true;
    field.focus();
  }
  function validate() {
    let first = null;
    for (const field of form.querySelectorAll('input,select')) {
      if (field.validity.valid) continue;
      const message = field.validity.valueMissing ? 'Vui lòng điền trường này.' : field.validity.rangeUnderflow ? 'Giá trị phải lớn hơn hoặc bằng 0.' : field.validity.stepMismatch ? 'Vui lòng nhập tối đa hai chữ số thập phân.' : 'Vui lòng nhập một giá trị hợp lệ.';
      const invalid=fieldError(field.name,message);
      first ||= invalid;
    }
    return first;
  }
  function loadScenario(scenario) {
    if (!scenario || pending) return;
    selected = scenario; clearErrors();
    const p = scenario.payload;
    const suffix = (crypto.randomUUID?.() || String(Date.now())).slice(0,8);
    for (const name of ['tx_type','amount','timestamp','oldbalanceOrg','newbalanceOrig','oldbalanceDest','newbalanceDest']) form.elements.namedItem(name).value = p[name];
    for (const name of ['card_id','merchant_id','device_id','location_id','ip_address']) {
      form.elements.namedItem(name).value = name==='ip_address' ? p.extras[name] : `${p.extras[name]}_${suffix}`;
    }
    form.elements.namedItem('is_fraud').value = '';
    document.querySelectorAll('[data-scenario]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scenario===scenario.key)));
    text('scenario-note',scenario.description);
    result.classList.add('hidden'); empty.classList.remove('hidden');
    empty.textContent='Đầu vào đã sẵn sàng. Chạy giao dịch để xem kết quả tính trực tiếp.';
    text('result-title','Kết quả của giao dịch'); setStatus(''); preview();
  }
  function busy(value) {
    pending=value; form.setAttribute('aria-busy',String(value));
    form.querySelectorAll('input,select,button').forEach(node => { node.disabled=value; });
    document.querySelectorAll('[data-scenario]').forEach(node => { node.disabled=value; });
    submit.textContent=value ? 'Đang xử lý…' : 'Chạy giao dịch';
  }
  function showResult(data) {
    const p=data.prediction || {}, action=data.final_action;
    const execution=data.agent?.execution || {};
    const providerNames=(execution.providers_observed || []).join(', ');
    const executionLabel=!data.agent ? 'Không dùng ReAct để ra quyết định ở nhánh này.' : execution.external_response_observed ? `${providerNames ? providerNames+' · ' : ''}LLM qua API: đã nhận phản hồi trong giao dịch này.` : execution.heuristic_responses>0 ? 'ReAct heuristic local đã chạy; không gọi LLM ngoài.' : 'Chưa có bằng chứng thực thi LLM trong kết quả này.';
    text('execution-status',executionLabel);
    text('execution-counts',data.agent ? Object.keys(execution).length ? `${execution.tools_executed?.length || 0} công cụ đã chạy · ${execution.heuristic_responses || 0} phản hồi heuristic · ${execution.external_responses || 0} phản hồi LLM qua API.` : 'Kết quả này chưa có metadata thực thi để đối chiếu số lượt gọi.' : p.route==='high' && action==='block' ? 'Nhánh cao chốt quyết định theo chính sách. Tác vụ ghi hậu kiểm chạy riêng; xem trạng thái thực thi để đối chiếu.' : 'XGBoost và chính sách phân luồng đã xử lý giao dịch.');
    text('agent-audit-json',JSON.stringify(data.agent || {decision_agent_used:false},null,2));
    function evidenceList(id, rows, fallback) {
      const list=byId(id); list.replaceChildren();
      (rows.length ? rows : [fallback]).forEach(value => { const item=document.createElement('li'); item.textContent=value; list.append(item); });
    }
    evidenceList('supporting-evidence',(data.narrative?.supporting_evidence || []).map(item=>`${item.text} [${item.source}]`),'Chưa có tín hiệu bổ sung trong kết quả tra cứu.');
    evidenceList('mitigating-evidence',(data.narrative?.mitigating_evidence || []).map(item=>`${item.text} [${item.source}]`),'Chưa có bằng chứng đối chiếu từ công cụ; không suy ra giao dịch an toàn.');
    evidenceList('model-evidence',(data.narrative?.model_evidence || []).map(item=>`${item.label}: ${item.direction} (${Number(item.impact)>=0?'+':''}${number(item.impact,4)}).`),'Không có dữ liệu SHAP trong kết quả này.');
    result.classList.remove('hidden'); empty.classList.add('hidden');
    text('summary-score',number(p.score)); text('summary-raw',probability(p.raw_probability));
    text('summary-route',routes[p.route] || p.route || '—'); text('summary-action',labels[action] || action);
    text('summary-latency',`${number(data.end_to_end_latency_ms,2)} ms`);
    text('final-note',data.final_note || ''); text('human-explanation',data.narrative?.human_readable_explanation || data.final_note || '');
    text('analyst-report',data.narrative?.analyst_report || 'Nhánh này không gọi tác tử điều tra.');
    text('dashboard-summary',data.narrative?.dashboard_summary || '');
    text('anomaly-explanation',`Anomaly score: ${number(p.anomaly_score)}. ${p.anomaly_flag ? 'Có cờ bất thường. Tín hiệu hỗ trợ bước điều tra; chưa phải nhãn gian lận.' : 'Chưa vượt ngưỡng cảnh báo.'}`);
    text('summary-route-pill',`Nhánh ${routes[p.route] || p.route}`);
    text('summary-raw-pill',`Xác suất gốc ${probability(p.raw_probability)}`);
    tone(byId('decision-card'),action); tone(byId('summary-route-pill'),p.route);
    ['input','features','model','decision'].forEach(step => { byId(`flow-${step}`).dataset.state='done'; });
    byId('flow-agent').dataset.state=data.agent ? 'done' : 'skip';
    text('agent-step-text',data.agent ? (data.agent.fallback_used ? 'Điều tra dùng phương án dự phòng' : execution.external_response_observed ? 'ReAct qua API đã phản hồi' : execution.heuristic_responses>0 ? 'ReAct heuristic local đã chạy' : 'Chưa xác minh backend ReAct') : 'Bỏ qua ReAct ở nhánh này');
    text('decision-step-text',labels[action] || action);
    byId('open-dashboard-case').href=`/dashboard/html?tx_id=${encodeURIComponent(data.event.tx_id)}`;
    byId('open-review-case').hidden=!['review','step_up'].includes(action);
    byId('open-review-case').href=`/reviews/pending?tx_id=${encodeURIComponent(data.event.tx_id)}`;
    setStatus(`Đã xử lý · ${labels[action] || action} · nhánh ${routes[p.route] || p.route}.`);
  }
  form.addEventListener('submit',async event => {
    event.preventDefault(); if (pending) return;
    clearErrors(); const invalid=validate();
    if (invalid) { setStatus('Vui lòng sửa thông tin được đánh dấu.',true); focusField(invalid); return; }
    const data=payload(); preview(); busy(true); setStatus('Đang chấm điểm, giải thích và xử lý nhánh phù hợp…');
    result.classList.add('hidden'); empty.classList.remove('hidden'); empty.textContent='Đang xử lý giao dịch. Kết quả sẽ hiển thị khi các bước thực sự hoàn tất.';
    let firstInvalid=null, succeeded=false;
    try {
      const response=await fetch('/gateway/transaction',{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify(data)});
      let body; try { body=await response.json(); } catch { throw new Error('Chưa đọc được kết quả từ máy chủ. Vui lòng kiểm tra trang Giám sát trước khi gửi lại.'); }
      if (!response.ok) {
        if (Array.isArray(body.detail)) {
          body.detail.forEach(error => {
            const name=error.loc?.at(-1);
            const message=error.type==='greater_than_equal' ? 'Giá trị phải lớn hơn hoặc bằng 0.' : error.type==='finite_number' ? 'Vui lòng nhập số hữu hạn.' : 'Giá trị chưa hợp lệ. Vui lòng kiểm tra lại.';
            const field=fieldError(name,message); firstInvalid ||= field;
          });
          throw new Error('Vui lòng sửa thông tin được đánh dấu.');
        }
        if (typeof body.detail==='string' && body.detail.includes('timestamp')) firstInvalid=fieldError('timestamp','Thời điểm chưa đúng định dạng ISO 8601. Ví dụ: 2025-01-01T14:00:00+00:00.');
        throw new Error(firstInvalid ? 'Vui lòng sửa thời điểm giao dịch.' : (typeof body.detail==='string' ? body.detail : 'Chưa xử lý được giao dịch. Dữ liệu nhập vẫn được giữ nguyên.'));
      }
      showResult(body); succeeded=true;
    } catch (error) {
      setStatus(error instanceof TypeError ? 'Không kết nối được máy chủ. Dữ liệu nhập vẫn được giữ nguyên; kiểm tra trang Giám sát trước khi gửi lại.' : error.message || 'Chưa xử lý được giao dịch.',true);
      empty.textContent='Chưa có kết quả mới. Hãy kiểm tra thông báo bên cạnh nút chạy giao dịch.';
    } finally {
      busy(false);
      if (firstInvalid) focusField(firstInvalid);
      if (succeeded) {
        text('result-title',`Kết quả: ${byId('summary-action').textContent}`);
        byId('result-title').focus({preventScroll:true});
        byId('result-title').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
      }
    }
  });
  form.addEventListener('input',()=>{ if (!pending) preview(); });
  document.querySelectorAll('[data-scenario]').forEach(button => button.addEventListener('click',()=>loadScenario(scenarios.find(item=>item.key===button.dataset.scenario))));
  reset.addEventListener('click',()=>loadScenario(selected));
  loadScenario(selected);
})();
