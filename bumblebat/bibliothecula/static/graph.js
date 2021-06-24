"use strict";

var color = (function(){
  const scale = d3.scaleOrdinal(d3.schemeCategory10);
  scale.domain([...Array(1000).keys()]);
  return d => scale(d.group);
})();

var height = 380;
var width = 500;

var chart = function(data) {
  const svg = d3.create("svg")
    .attr("viewBox", [-width / 2, -height / 2, width, height]);
  var container = svg.append("g");
  svg.call(d3.zoom()
    .scaleExtent([.1, 4])
    .on("zoom", function(event) { container.attr("transform", event.transform); })
  );
  const links = data.links.map(d => Object.create(d));
  const nodes = data.nodes.map(d => Object.create(d));

  var adjlist = new Map();

  links.forEach(function(d) {
    adjlist.set(d.source + "-" + d.target,true);
    adjlist.set(d.target + "-" + d.source, true);
  });

  function neigh(a, b) {
    return a == b || adjlist.get(nodes[a].id + "-" + nodes[b].id);
  }

  var simulation = d3.forceSimulation()
    .force("link", d3.forceLink().id(function(d) { return d.id; }).distance(function(d) {return 25.0;}))
    .force("charge", d3.forceManyBody())
    .force("center", d3.forceCenter(0,0))
    .force("x", d3.forceX())
    .force("y", d3.forceY());


  var link = container.append("g")
    .attr("class", "links")
    .selectAll("line")
    .data(links)
    .enter().append("line")
    .attr("stroke-width", function(d) { return Math.sqrt(d.value); });

  var node = container.append("g")
    .attr("class", "nodes")
    .selectAll("g")
    .data(nodes)
    .enter().append("g")

  node.on("mouseover", focus).on("mouseout", unfocus);
  var circles = node.append("circle")
    .attr("r", 5)
    .attr("fill", function(d) { return color(d); })
    .call(d3.drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended)
    );

  var margin = {top: 30, right: 20, bottom: 30, left: 20},
    barHeight = 20,
    barWidth = (width - margin.left - margin.right) * 0.8;
  var labelNode = node.append("svg:a")
    .attr("xlink:href", function(d){return TAG_D3_URL+d.id;})
    .append("text")
    .text(function(d) {
      return d.id;
    })
    .attr('x', 6)
    .attr('y', 3);

  node.append("title")
    .text(function(d) { return d.id; });

  simulation
    .nodes(nodes)
    .on("tick", ticked);

  simulation.force("link")
    .links(links);

  function focus(d) {
    var index = d3.select(event.target).datum().index;
    node.style("opacity", function(o) {
      return neigh(index, o.index) ? 1 : 0.1;
    });
    labelNode.attr("display", function(o) {
      return neigh(index, o.index) ? "block": "none";
    }).attr("text-decoration", function(o) {
      return neigh(index, o.index) ? "underline": "none";
    }).attr("color", function(o) {
      return neigh(index, o.index) ? "blue": "black";
    });
    link.style("opacity", function(o) {
      return o.source.index == index || o.target.index == index ? 1 : 0.1;
    });
  }

  function unfocus() {
    labelNode.attr("display", "block");
    node.style("opacity", 1);
    link.style("opacity", 1);
  }

  function ticked() {
    link
      .attr("x1", function(d) { return d.source.x; })
      .attr("y1", function(d) { return d.source.y; })
      .attr("x2", function(d) { return d.target.x; })
      .attr("y2", function(d) { return d.target.y; });

    node
      .attr("transform", function(d) {
        return "translate(" + d.x + "," + d.y + ")";
      })
  }

  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }

  function dragged(event,d) {
    d.fx = event.x;
    d.fy = event.y;
  }

  function dragended(event,d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }

  return svg.node();
};

window.addEventListener('load', (event) => {
  var element = document.querySelector("#d3-box");
  var node_data =  JSON.parse(document.getElementById("node-data").text);
  element.appendChild(chart(node_data));
});
