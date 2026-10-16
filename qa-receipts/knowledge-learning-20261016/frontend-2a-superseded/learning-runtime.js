    function cancelLearning() {
      if (learningTimer) root.clearTimeout(learningTimer); learningTimer = null;
      if (learningState) learningState.playing = false;
    }
    function learningRoute(replace = true) {
      if (!learningState || !root.history?.replaceState || !root.location || view !== 'knowledge') return;
      const event=learningState.model.events[learningState.index], item=event?.versionRecord || event?.item;
      if (!event) return;
      const params=new URLSearchParams();
      if(item?.knowledge_id && item?.version) { params.set('knowledge',item.knowledge_id);params.set('version',item.version);params.set('sha256',item.knowledge_sha256 || '');const definition=item.definition_sha256 || item.qualification?.definition_sha256;if(definition)params.set('definition',definition); }
      params.set('event',event.id);params.set('stage',String(learningState.stage));params.set('facet',knowledgeFacet);
      const fragment='#autonomous/knowledge?'+params;
      root.history[replace?'replaceState':'pushState'](null,'',root.location.pathname+root.location.search+fragment);routedFragment=fragment;
    }
    function synchronizeLearning(announce = false) {
      if (!learningState || view !== 'knowledge') return;
      const {model,index,stage,playing}=learningState, event=model.events[index], shell=host.querySelector('[data-au-learning]'), focus=host.querySelector('[data-au-learning-focus]');
      if(shell) { shell.dataset.auLearningEventId=event?.id || '';shell.dataset.auLearningKind=event?.kind || '';shell.dataset.auLearningPosition=String(index);shell.dataset.auLearningPlaying=String(playing);shell.dataset.auLearningSettled=String(stage===10&&!playing); }
      if(focus) { focus.dataset.auLearningStage=String(stage);for(const node of focus.querySelectorAll('[data-au-learning-reveal]')) { const waiting=stage<Number(node.dataset.auLearningReveal);node.setAttribute('data-au-learning-waiting',String(waiting));node.setAttribute('aria-hidden',String(waiting));node.inert=waiting; }for(const node of focus.querySelectorAll('[data-au-learning-check]')) node.setAttribute('data-au-check-shown',String(stage>=3+Number(node.dataset.auLearningCheck))); }
      const play=host.querySelector('[data-au-learning-play]');if(play){play.textContent=playing?'Pause':'Play recorded learning';play.setAttribute('aria-label',playing?'Pause recorded learning':'Play recorded learning');play.setAttribute('aria-pressed',String(playing));}
      const range=host.querySelector('[data-au-learning-scrub]');if(range){range.value=String(index);range.setAttribute('aria-valuetext',event?`${index+1} of ${model.events.length}: ${learningEventLabel(event)} · ${learningTime(event)}`:'No recorded events');}
      const position=host.querySelector('[data-au-learning-position]');if(position)position.textContent=event?`${index+1} / ${model.events.length} · ${learningEventLabel(event)}`:'No recorded events';
      for(const node of host.querySelectorAll('[data-au-learning-event]'))node.setAttribute('aria-current',Number(node.dataset.auLearningEvent)===index?'step':'false');
      if(announce && event && learningState.announced!==event.id) { const live=host.querySelector('[data-au-learning-announcement]');if(live)live.textContent=`${learningEventLabel(event)}. ${procedureLabel(event.versionRecord || event.item)}. ${learningTime(event)}.`;learningState.announced=event.id; }
    }
    function selectLearning(index, stage = 10, remember = false, announce = true) {
      if (!learningState || !learningState.model.events.length) return;
      const next=Math.max(0,Math.min(learningState.model.events.length-1,Number(index)||0));
      const changed=learningState.index!==next || !host.querySelector('[data-au-learning-focus]')?.firstElementChild;
      learningState.index=next;learningState.stage=Math.max(0,Math.min(10,Number(stage)||0));
      const pane=host.querySelector('[data-au-learning-focus]');
      if(pane && (changed || learningState.facet!==knowledgeFacet)) {pane.innerHTML=knowledgeLearningFocus(learningState.model,learningState.model.events[next],knowledgeFacet);learningState.facet=knowledgeFacet;}
      synchronizeLearning(announce);if(remember)learningRoute();
    }
    function pauseLearning(remember = true) {if(!learningState)return;cancelLearning();synchronizeLearning();if(remember)learningRoute();}
    function playLearning() {
      if(!learningState || !learningState.model.frames.length || view!=='knowledge')return;
      cancelLearning();
      const {model}=learningState;
      let frame=model.frames.findIndex(row=>row.index===learningState.index&&row.stage>=learningState.stage);
      if(frame<0 || frame===model.frames.length-1)frame=0;
      learningState.playing=true;
      function tick() {
        if(disposed || view!=='knowledge' || !learningState?.playing || doc.hidden || pendingRoute())return;
        const row=model.frames[frame++];
        if(!row) {learningState.playing=false;learningState.stage=10;synchronizeLearning();learningRoute();return;}
        selectLearning(row.index,row.stage,true);
        learningTimer=root.setTimeout(tick,row.duration);
      }
      tick();
    }
    function renderKnowledge(data, pin, initial = false, preference = null) {
      const open = new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(element => element.dataset.auDisclosure));
      const model=knowledgeLearningModel(data), matching=pin?model.versions.find(item=>knowledgePinMatches(item,pin)):null;
      const pinnedEvent=matching?model.events.findIndex(event=>event.kind==='knowledge.published'&&event.versionRecord===matching&&!event.refused):-1;
      const explicit=preference?.event ? model.events.findIndex(event=>event.id===preference.event):-1;
      const first=!learningVisited && !pin && !preference?.event && !reduced?.matches && model.events.some(event=>event.recorded);
      const preserve=learningState?.data===data && !initial && !preference;
      const position=preserve?{index:learningState.index,stage:learningState.stage}:explicit>=0?{index:explicit,stage:preference.stage??10}:pinnedEvent>=0?{index:pinnedEvent,stage:10}:pin?null:first?{index:0,stage:0}:null;
      const sameData=renderedKnowledge===data && host.querySelector('[data-au-learning]');
      if (!sameData || initial) {
        cancelLearning();host.innerHTML=knowledgeMarkup(data,claims,pin,knowledgeFacet,position);
        const fallback=model.events.findIndex(event=>event.kind==='knowledge.published'&&!event.refused&&event.versionRecord===[...model.versions].sort((a,b)=>String(name(a)).localeCompare(String(name(b)))||Number(b.version)-Number(a.version))[0]);
        learningState={data,model,index:position?.index??Math.max(0,fallback),stage:position?.stage??10,playing:false,facet:knowledgeFacet,announced:null};
        renderedKnowledge=data;knowledgePin=pin;
        for(const disclosure of host.querySelectorAll('[data-au-disclosure]'))disclosure.open=open.has(disclosure.dataset.auDisclosure);
        interact(host);if(initial)focusTitle();
      } else {knowledgePin=pin;if(position)selectLearning(position.index,position.stage,false,false);else if(learningState?.facet!==knowledgeFacet)selectLearning(learningState.index,learningState.stage,false,false);}
      synchronizeKnowledgeRead();synchronizeLearning();
      host.querySelectorAll('[data-pinned]').forEach(row=>row.removeAttribute('data-pinned'));
      if(pin && !matching) {notice('The exact reused knowledge version is not available in this record.',true);return false;}
      if(pin && matching) {
        const row=[...host.querySelectorAll('[data-au-knowledge-identity]')].find(element=>element.dataset.auKnowledgeIdentity===`${pin.knowledge_id}:${pin.version}`);
        if(row){row.setAttribute('data-pinned','true');row.setAttribute('tabindex','-1');row.focus({preventScroll:true});row.scrollIntoView?.({block:'nearest',behavior:'instant'});}
      }
      if(first){learningVisited=true;playLearning();}else if(model.events.length)learningVisited=true;
      return true;
    }
