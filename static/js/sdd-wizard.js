(function(){
  function bindGroup(group){
    const rows=group.querySelector('[data-repeat-rows]');
    const add=group.querySelector('[data-add-row]');
    if(!rows||!add)return;
    add.addEventListener('click',function(){
      const source=rows.querySelector('[data-repeat-row]');
      if(!source)return;
      const clone=source.cloneNode(true);
      clone.querySelectorAll('input, textarea, select').forEach(function(field){field.value='';});
      rows.appendChild(clone);
    });
    rows.addEventListener('click',function(event){
      const button=event.target.closest('[data-remove-row]');
      if(!button)return;
      const row=button.closest('[data-repeat-row]');
      if(!row)return;
      if(rows.querySelectorAll('[data-repeat-row]').length===1){row.querySelectorAll('input, textarea, select').forEach(function(field){field.value='';});}
      else row.remove();
    });
  }
  document.querySelectorAll('[data-repeat-group]').forEach(bindGroup);
})();
