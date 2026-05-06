let canvas;
let statusMessage = "Draw a Chinese character, then add it.";
let isProcessing = false;

function setup() {
  const canvasWidth = getResponsiveCanvasWidth();
  const canvasHeight = Math.round(canvasWidth * 1.3);

  canvas = createCanvas(canvasWidth, canvasHeight);
  canvas.parent("canvas-holder");

  resetDrawingCanvas();

  stroke(0);
  strokeWeight(12);
  strokeCap(ROUND);
}

function getResponsiveCanvasWidth() {
  const maxWidth = 500;
  const availableWidth = window.innerWidth * 0.75;

  if (window.innerWidth < 700) {
    return Math.min(window.innerWidth * 0.82, maxWidth);
  }

  return Math.min(availableWidth, maxWidth);
}

function windowResized() {
  const newWidth = getResponsiveCanvasWidth();
  const newHeight = Math.round(newWidth * 1.3);

  resizeCanvas(newWidth, newHeight);
  resetDrawingCanvas();
}

function resetDrawingCanvas() {
  background(255);

  push();
  stroke(220);
  strokeWeight(1);

  line(width / 3, 0, width / 3, height);
  line((width * 2) / 3, 0, (width * 2) / 3, height);
  line(0, height / 3, width, height / 3);
  line(0, (height * 2) / 3, width, (height * 2) / 3);

  pop();

  drawStatusMessage();
}

function draw() {
  if (
    !isProcessing &&
    mouseIsPressed &&
    mouseX >= 0 &&
    mouseX <= width &&
    mouseY >= 0 &&
    mouseY <= height &&
    pmouseX >= 0 &&
    pmouseX <= width &&
    pmouseY >= 0 &&
    pmouseY <= height
  ) {
    stroke(0);
    strokeWeight(Math.max(8, width * 0.025));
    strokeCap(ROUND);
    line(pmouseX, pmouseY, mouseX, mouseY);
  }
}

function touchMoved() {
  return false;
}

function drawStatusMessage() {
  push();

  noStroke();
  fill(255);
  rect(0, height - 38, width, 38);

  fill(40);
  textSize(Math.max(13, width * 0.032));
  textAlign(LEFT, CENTER);
  text(statusMessage, 16, height - 19);

  pop();
}

function setStatus(message) {
  statusMessage = message;
  drawStatusMessage();

  const statusElement = document.getElementById("status");
  if (statusElement) {
    statusElement.textContent = message;
  }
}

function clearCanvas() {
  resetDrawingCanvas();
  setStatus("Draw a Chinese character, then add it.");
}

async function submitDrawing() {
  if (isProcessing) return;

  const button = document.getElementById("add-character-btn");

  try {
    isProcessing = true;

    if (button) {
      button.disabled = true;
      button.textContent = "Recognizing...";
    }

    setStatus("Recognizing character...");

    const dataUrl = canvas.elt.toDataURL("image/png");

    const response = await fetch("/add_character", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        image: dataUrl,
        canvas_width: width,
        canvas_height: height
      })
    });

    const result = await response.json();
    console.log(result);

    updateDebugData(result);

    if (result.error) {
      setStatus(`Error: ${result.error}`);
      return;
    }

    if (result.scene_elements) {
      updateElementList(result.scene_elements);
    }

    clearCanvas();
    setStatus(`Added "${result.character}" → ${result.meaning}. Add another or generate artwork.`);
  } catch (error) {
    console.error(error);
    setStatus("Something went wrong. Check the terminal and try again.");
  } finally {
    isProcessing = false;

    if (button) {
      button.disabled = false;
      button.textContent = "Add Character";
    }
  }
}

async function generateArtwork() {
  if (isProcessing) return;

  const button = document.getElementById("generate-artwork-btn");
  const generated = document.getElementById("generated");

  try {
    isProcessing = true;

    if (button) {
      button.disabled = true;
      button.textContent = "Generating...";
    }

    if (generated) {
      generated.style.opacity = 0.35;
    }

    setStatus("Generating ink artwork from your added characters...");

    const response = await fetch("/generate_scene", {
      method: "POST"
    });

    const result = await response.json();
    console.log(result);

    updateDebugData(result);

    if (result.error) {
      setStatus(`Error: ${result.error}`);
      return;
    }

    if (result.image_path && generated) {
      generated.onload = () => {
        generated.style.opacity = 1;
      };

      const freshImagePath = "/" + result.image_path + "?t=" + Date.now();

      generated.src = freshImagePath;

      const downloadLink = document.getElementById("download-artwork-link");
      if (downloadLink) {
        downloadLink.href = "/" + result.image_path;
      }
    }

    if (result.scene_elements) {
      updateElementList(result.scene_elements);
    }

    setStatus("Artwork generated. You can add more characters or reset.");
  } catch (error) {
    console.error(error);
    setStatus("Something went wrong during generation.");
  } finally {
    isProcessing = false;

    if (button) {
      button.disabled = false;
      button.textContent = "Generate Artwork";
    }
  }
}

async function resetArtwork() {
  await fetch("/reset_scene", {
    method: "POST"
  });

  clearCanvas();

  const generated = document.getElementById("generated");
  if (generated) {
    generated.src = "";
  }

  const output = document.getElementById("result-output");
  if (output) {
    output.textContent = "";
  }

  updateElementList([]);
  setStatus("Reset complete. Draw a new character.");
}

function updateElementList(elements) {
  const list = document.getElementById("element-list");

  if (!list) {
    return;
  }

  list.innerHTML = "";

  elements.forEach((element, index) => {
    const item = document.createElement("li");

    item.textContent =
      `${index + 1}. ${element.character} — ${element.meaning} → ${element.visual}`;

    list.appendChild(item);
  });
}

function updateDebugData(result) {
  const output = document.getElementById("result-output");

  if (output) {
    output.textContent = JSON.stringify(result, null, 2);
  }
}