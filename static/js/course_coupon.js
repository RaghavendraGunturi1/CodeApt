(function(){
    // helper to read csrftoken
    function getCSRF(){
        const name='csrftoken='; const ca=document.cookie.split(';');
        for(let i=0;i<ca.length;i++){let c=ca[i].trim(); if(c.indexOf(name)===0) return decodeURIComponent(c.substring(name.length));}
        return '';
    }

    function showFeedback(text, cls){
        const fb = document.getElementById('coupon-feedback');
        if(!fb) return;
        fb.classList.remove('d-none','text-success','text-danger','text-muted');
        if(cls) fb.classList.add(cls);
        fb.innerText = text;
    }

    async function applyCoupon(code, subjectSlug){
        const csrftoken = getCSRF();
        try{
            const res = await fetch(`/apply-coupon/${subjectSlug}/`, {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken': csrftoken},
                body: JSON.stringify({coupon: code})
            });
            const data = await res.json().catch(()=>({success:false, message:'Invalid server response'}));
            return {status: res.status, data};
        }catch(e){
            return {status: 0, data: {success:false, message: 'Network error'}};
        }
    }

    function attach(){
        const applyBtn = document.getElementById('apply-coupon-btn');
        const couponInput = document.getElementById('coupon-input');
        const buyBtn = document.getElementById('buy-now-btn');
        if(!applyBtn || !couponInput) return;
        const subjectSlug = document.body.getAttribute('data-subject-slug') || (function(){
            try{
                const url = new URL(buyBtn.href, window.location.origin);
                const parts = url.pathname.split('/').filter(Boolean);
                return parts.length >= 2 ? parts[1] : '';
            }catch(e){ return ''; }
        })();

        applyBtn.addEventListener('click', async function(){
            console.log('apply button clicked');
            const code = couponInput.value.trim();
            if(!code){ showFeedback('Enter a coupon code', 'text-danger'); return; }
            applyBtn.disabled = true; showFeedback('Applying coupon...', 'text-muted');
            const result = await applyCoupon(code, subjectSlug);
            applyBtn.disabled = false; console.log('apply result', result);
            if(result.data && result.data.success){
                showFeedback(`Coupon applied: -₹${result.data.discount_amount} · New price: ₹${result.data.new_price}`, 'text-success');
                if(buyBtn && result.data.coupon_code){ const url = new URL(buyBtn.href, window.location.origin); url.searchParams.set('coupon', result.data.coupon_code); buyBtn.href = url.toString(); }
                const priceCurrent = document.getElementById('price-current'); if(priceCurrent) priceCurrent.innerText = `₹${result.data.new_price}`;
            }else{
                showFeedback(result.data && result.data.message ? result.data.message : 'Coupon invalid', 'text-danger');
            }
        });
    }

    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach); else attach();
})();
