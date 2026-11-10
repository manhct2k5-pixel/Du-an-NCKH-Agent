try {
  const receipt=sessionStorage.getItem('review-receipt');
  if (receipt) {
    sessionStorage.removeItem('review-receipt');
    const notice=document.createElement('p'); notice.className='evidence-scope';notice.setAttribute('role','status');notice.textContent=receipt;
    document.querySelector('.app-header')?.after(notice);
  }
} catch { /* Storage is optional; reviewing still works when unavailable. */ }
document.querySelectorAll('.review-form').forEach(form => {
  let pending=false;
  form.addEventListener('submit',async event => {
    event.preventDefault(); if (pending || !form.reportValidity()) return;
    const fields=new FormData(form), action=fields.get('action');
    if (!window.confirm(`Lưu quyết định ${action==='block'?'chặn':'thông qua'} cho ${form.dataset.txId}?`)) return;
    const status=form.querySelector('[role=status]'), button=form.querySelector('button');
    const payload={action,reviewer:'demo_nckh',note:fields.get('note'),actual_label:fields.get('actual_label')===''?null:Number(fields.get('actual_label'))};
    pending=true; button.disabled=true; button.textContent='Đang lưu…'; form.setAttribute('aria-busy','true');
    status.textContent='Đang ghi nhận quyết định và phản hồi.';status.classList.remove('is-error');
    try {
      const response=await fetch(`/reviews/${encodeURIComponent(form.dataset.txId)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const result=await response.json().catch(()=>({}));
      if (!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'Chưa lưu được. Vui lòng kiểm tra thông tin hoặc tải lại hàng đợi.');
      status.textContent=`Đã lưu quyết định. ${result.runtime_feedback_applied?'Nhãn đã cập nhật vào lịch sử online.':'Chưa cập nhật nhãn vào lịch sử online.'} Đang tải lại hàng đợi…`;
      try { sessionStorage.setItem('review-receipt',`Đã xác minh ${form.dataset.txId}: ${action==='block'?'chặn':'thông qua'}. ${result.runtime_feedback_applied?'Nhãn đã cập nhật vào lịch sử online.':'Chưa cập nhật nhãn vào lịch sử online.'}`); } catch { /* Optional receipt only. */ }
      form.querySelectorAll('input,select,textarea').forEach(node=>{node.disabled=true;});
      window.location.assign('/reviews/pending');
    } catch (error) {
      status.textContent=error.message || 'Không kết nối được máy chủ.';status.classList.add('is-error');
      pending=false;button.disabled=false;button.textContent='Xác nhận và lưu phản hồi';form.setAttribute('aria-busy','false');
    }
  });
});
