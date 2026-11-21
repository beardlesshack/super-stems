const SVG_NS = "http://www.w3.org/2000/svg";
const NAME = "Dennis";
const FLOWER = "june";
const FONT_SIZE = 42;
const TOP_LEAD = 22;
const BOTTOM_TAIL = 20;
const FLOWER_X = 367;
const FLOWER_Y = 52;
const FLOWER_WIDTH = 166;
const FLOWER_HEIGHT = 249;

const svg = document.getElementById("stem-proof");
const plant = document.getElementById("plant-art");
const note = document.getElementById("render-note");

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, value));
  return node;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function makeStemPath(centerX, topY, span, bend) {
  const bottomY = topY + span;
  const quarter = span * .25;
  const mid = span * .5;
  return [
    `M ${centerX + bend * .25} ${bottomY}`,
    `C ${centerX - bend} ${bottomY - quarter}`,
    `${centerX + bend * .25} ${topY + span * .58}`,
    `${centerX} ${bottomY - mid}`,
    `C ${centerX - bend * .25} ${topY + span * .42}`,
    `${centerX + bend * .75} ${topY + quarter}`,
    `${centerX - bend * .15} ${topY}`
  ].join(" ");
}

function stableBend(name) {
  let hash = 0;
  for (const character of name) hash = (hash * 31 + character.charCodeAt(0)) | 0;
  return (hash & 1 ? 1 : -1) * (7 + (Math.abs(hash) % 4));
}

async function transparentFlower(source) {
  const image = new Image();
  image.src = source;
  await image.decode();

  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(image, 0, 0);

  const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
  for (let index = 0; index < pixels.data.length; index += 4) {
    const red = pixels.data[index];
    const green = pixels.data[index + 1];
    const blue = pixels.data[index + 2];
    const high = Math.max(red, green, blue);
    const low = Math.min(red, green, blue);
    const chroma = high - low;
    const light = (red + green + blue) / 3;
    const colorAlpha = clamp(Math.round((chroma - 18) * 10), 0, 255);
    const inkAlpha = clamp(Math.round((170 - light) * 5), 0, 255);
    const petalAlpha = clamp(Math.round((light - 208) * 6), 0, 255);
    pixels.data[index + 3] = Math.max(colorAlpha, inkAlpha, petalAlpha);
  }
  context.putImageData(pixels, 0, 0);
  return canvas.toDataURL("image/png");
}

function addFlower(href) {
  const image = svgElement("image", {
    href,
    x: FLOWER_X,
    y: FLOWER_Y,
    width: FLOWER_WIDTH,
    height: FLOWER_HEIGHT,
    preserveAspectRatio: "xMidYMid meet",
    class: "flower-art"
  });
  plant.appendChild(image);
}

function addLettering() {
  const measure = svgElement("text", {
    x: -1000,
    y: -1000,
    "font-family": "Allura, cursive",
    "font-size": FONT_SIZE,
    "aria-hidden": "true"
  });
  measure.textContent = NAME;
  plant.appendChild(measure);

  const wordLength = measure.getComputedTextLength();
  measure.remove();

  const centerX = FLOWER_X + FLOWER_WIDTH * .49;
  const topY = FLOWER_Y + FLOWER_HEIGHT - 7;
  const targetLength = wordLength + TOP_LEAD + BOTTOM_TAIL;
  const bend = stableBend(`${FLOWER}:${NAME}`);
  let span = targetLength;
  let guideData = "";
  const guide = svgElement("path", { class: "guide-stem" });

  for (let iteration = 0; iteration < 5; iteration += 1) {
    guideData = makeStemPath(centerX, topY, span, bend);
    guide.setAttribute("d", guideData);
    const measuredLength = guide.getTotalLength();
    span *= targetLength / measuredLength;
  }
  guideData = makeStemPath(centerX, topY, span, bend);
  guide.setAttribute("d", guideData);
  const actualLength = guide.getTotalLength();

  guide.setAttribute("stroke-dasharray", `${BOTTOM_TAIL} ${wordLength} ${Math.max(0, actualLength - BOTTOM_TAIL - wordLength)}`);
  plant.appendChild(guide);

  const highlight = svgElement("path", { d: guideData, class: "guide-highlight" });
  highlight.setAttribute("stroke-dasharray", `${BOTTOM_TAIL} ${wordLength} ${Math.max(0, actualLength - BOTTOM_TAIL - wordLength)}`);
  plant.appendChild(highlight);

  const text = svgElement("text", { class: "name-lettering" });
  const textPath = svgElement("textPath", {
    href: "#stem-guide-path",
    startOffset: BOTTOM_TAIL,
    "text-anchor": "start"
  });
  textPath.textContent = NAME;
  text.appendChild(textPath);

  guide.setAttribute("id", "stem-guide-path");
  plant.appendChild(text);

  note.textContent = `${Math.round(actualLength)} px stem · ${Math.round(wordLength)} px lettering`;
}

async function render() {
  await document.fonts.load(`${FONT_SIZE}px Allura`);
  const flowerSource = `../final/static/flowers/${FLOWER}.png`;
  try {
    const cutout = await transparentFlower(flowerSource);
    addFlower(cutout);
  } catch (error) {
    const original = svgElement("image", {
      href: flowerSource,
      x: FLOWER_X,
      y: FLOWER_Y,
      width: FLOWER_WIDTH,
      height: FLOWER_HEIGHT,
      preserveAspectRatio: "xMidYMid meet",
      class: "flower-art"
    });
    original.style.mixBlendMode = "multiply";
    plant.appendChild(original);
    note.textContent = "Flower loaded with paper blend";
  }
  addLettering();
}

render().catch(error => {
  note.textContent = `Preview could not render: ${error.message}`;
  console.error(error);
});

