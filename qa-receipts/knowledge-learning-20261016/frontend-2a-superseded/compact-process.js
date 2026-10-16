  function learningProcessMarkup(version) {
    const layout=layoutGraph(version.graph || {nodes:[],edges:[]}),positions=new Map(layout.nodes.map((node,index)=>[node.node_id,index+1]));
    return `<div class="au-learning-process-map" aria-label="Recorded process and dependencies"><p>Dependencies refer to the recorded step numbers.</p><ol>${layout.nodes.map((node,index)=>`<li data-au-procedure-node="${h(node.node_id)}" style="--au-learning-rank:${index}"><h3><span>${index+1}.</span> ${h(name(node))}</h3>${list(layout.parents.get(node.node_id)).length?`<p>Requires ${h(layout.parents.get(node.node_id).map(id=>positions.get(id)).join(' + '))}</p>`:'<p>Entry step</p>'}</li>`).join('') || '<li>No process definition recorded.</li>'}</ol></div>`;
  }
