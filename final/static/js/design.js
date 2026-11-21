document.addEventListener("DOMContentLoaded", () => {
  const config = window.NameSproutsConfig;
  const form = document.getElementById("flower-form");
  const saveForm = document.getElementById("save-form");
  const nameInput = document.getElementById("sprout-name");
  const monthInput = document.getElementById("sprout-month");
  const layoutSelect = document.getElementById("layout-select");
  const paperSelect = document.getElementById("paper-select");
  const titleInput = document.getElementById("design-title");
  const sproutList = document.getElementById("sprout-list");
  const canvas = document.getElementById("proof-canvas");
  const countLabel = document.getElementById("sprout-count");
  const emptyList = document.getElementById("empty-list");
  const saveButton = document.getElementById("save-proof");
  const storageKey = "namesprouts-composer";
  let sprouts = [];
  let designId = "";

  const dimensions = {
    "letter-landscape": [1100, 850],
    "letter-portrait": [850, 1100],
    square: [1000, 1000]
  };

  function restoreDraft() {
    if (config.initialDesign) {
      sprouts = config.initialDesign.sprouts || [];
      designId = config.initialDesign.id || "";
      titleInput.value = config.initialDesign.title || "";
      layoutSelect.value = config.initialDesign.layout || "row";
      paperSelect.value = config.initialDesign.paper_size || "letter-landscape";
      localStorage.removeItem(storageKey);
      return;
    }
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (saved) {
        sprouts = Array.isArray(saved.sprouts) ? saved.sprouts : [];
        designId = saved.designId || "";
        titleInput.value = saved.title || "";
        layoutSelect.value = saved.layout || "row";
        paperSelect.value = saved.paperSize || "letter-landscape";
      }
    } catch {
      localStorage.removeItem(storageKey);
    }
  }

  function storeDraft() {
    localStorage.setItem(storageKey, JSON.stringify({
      sprouts,
      designId,
      title: titleInput.value,
      layout: layoutSelect.value,
      paperSize: paperSelect.value
    }));
  }

  function addSvgElement(tag, attributes, parent) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    parent.appendChild(element);
    return element;
  }

  function getRows() {
    if (layoutSelect.value === "two-rows" && sprouts.length > 1) {
      const splitAt = Math.ceil(sprouts.length / 2);
      return [
        { items: sprouts.slice(0, splitAt), centerY: 0.28 },
        { items: sprouts.slice(splitAt), centerY: 0.70 }
      ].filter(row => row.items.length);
    }
    return [{ items: sprouts, centerY: 0.49 }];
  }

  function drawProof() {
    const size = dimensions[paperSelect.value];
    const width = size[0];
    const height = size[1];
    canvas.setAttribute("viewBox", "0 0 " + width + " " + height);
    canvas.replaceChildren();
    addSvgElement("image", {
      href: config.paperUrl, x: 0, y: 0, width: width, height: height,
      preserveAspectRatio: "xMidYMid slice"
    }, canvas);

    getRows().forEach(row => {
      const count = row.items.length;
      const slotWidth = (width - 80) / count;
      const tileWidth = Math.min(235, slotWidth + 26);
      const tileHeight = tileWidth * 1.38;
      const top = height * row.centerY - tileHeight * 0.49;
      row.items.forEach((sprout, index) => {
        const centerX = width * (index + 0.5) / count;
        const offset = layoutSelect.value === "staggered" && index % 2 ? 24 : 0;
        const imageTop = top + offset;
        const image = addSvgElement("image", {
          href: config.flowersUrl + "?month=" + sprout.month,
          x: centerX - tileWidth / 2, y: imageTop,
          width: tileWidth, height: tileHeight,
          preserveAspectRatio: "xMidYMax meet"
        }, canvas);
        image.style.mixBlendMode = "multiply";
        const nameY = imageTop + tileHeight * 0.82;
        const fontSize = Math.min(28, Math.max(10, tileHeight * 0.37 / Math.max(sprout.name.length * 0.56, 1)));
        const label = addSvgElement("text", {
          x: centerX, y: nameY,
          "text-anchor": "middle",
          "dominant-baseline": "middle",
          "font-family": "Allura, Dancing Script, cursive",
          "font-size": fontSize,
          fill: "#24231f",
          transform: "rotate(-90 " + centerX + " " + nameY + ")"
        }, canvas);
        label.textContent = sprout.name;
      });
    });
    canvas.setAttribute("aria-label", "Proof with " + sprouts.length + " flower" + (sprouts.length === 1 ? "" : "s"));
    countLabel.textContent = sprouts.length + " / " + config.maxSprouts;
    emptyList.hidden = sprouts.length > 0;
    saveButton.disabled = sprouts.length === 0;
    renderList();
  }

  function renderList() {
    sproutList.replaceChildren();
    sprouts.forEach((sprout, index) => {
      const item = document.createElement("li");
      item.className = "sprout-list-item";
      const flower = document.createElement("img");
      flower.src = config.flowersUrl + "?month=" + sprout.month;
      flower.alt = "";
      const name = document.createElement("span");
      name.className = "sprout-list-name";
      name.textContent = sprout.name;
      const month = document.createElement("small");
      month.textContent = sprout.month[0].toUpperCase() + sprout.month.slice(1);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-sprout";
      remove.setAttribute("aria-label", "Remove " + sprout.name);
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        sprouts.splice(index, 1);
        storeDraft();
        drawProof();
      });
      item.append(flower, name, month, remove);
      sproutList.appendChild(item);
    });
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    const name = nameInput.value.trim();
    const month = monthInput.value;
    if (!name || !month) return;
    if (sprouts.length >= config.maxSprouts) {
      alert("A page can hold up to " + config.maxSprouts + " flowers.");
      return;
    }
    sprouts.push({ name: name, month: month });
    nameInput.value = "";
    monthInput.value = "";
    nameInput.focus();
    storeDraft();
    drawProof();
  });

  [layoutSelect, paperSelect].forEach(select => select.addEventListener("change", () => {
    storeDraft();
    drawProof();
  }));
  titleInput.addEventListener("input", storeDraft);

  saveForm.addEventListener("submit", event => {
    if (!sprouts.length) {
      event.preventDefault();
      return;
    }
    document.getElementById("sprouts-json").value = JSON.stringify(sprouts);
    document.getElementById("saved-layout").value = layoutSelect.value;
    document.getElementById("saved-paper-size").value = paperSelect.value;
    document.getElementById("saved-title").value = titleInput.value;
    document.getElementById("saved-design-id").value = designId;
    storeDraft();
    saveButton.disabled = true;
    saveButton.textContent = "Saving proof…";
  });

  restoreDraft();
  drawProof();
});

