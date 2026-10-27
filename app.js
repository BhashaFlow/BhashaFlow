const micBtn = document.getElementById("micBtn");
const mockRunBtn = document.getElementById("mockRunBtn");
const transcriptEl = document.getElementById("transcript");
const statusEl = document.getElementById("hud-status");
const stepsFeed = document.getElementById("stepsFeed");
const waveBars = document.querySelectorAll("#waveBars span");

let isListening = false;
let waveInterval;

micBtn.addEventListener("click", () => {
    isListening = !isListening;
    if (isListening) {
        statusEl.innerText = "STATUS: LISTENING";
        statusEl.style.color = "#38bdf8";
        transcriptEl.innerText = '"Extract latest report from Downloads and draft an email..."';
        startVisualizer();
    } else {
        statusEl.innerText = "STATUS: IDLE";
        stopVisualizer();
    }
});

mockRunBtn.addEventListener("click", () => {
    runMockWorkflow();
});

function startVisualizer() {
    waveInterval = setInterval(() => {
        waveBars.forEach(bar => {
            const h = Math.floor(Math.random() * 26) + 6;
            bar.style.height = `${h}px`;
        });
    }, 120);
}

function stopVisualizer() {
    clearInterval(waveInterval);
    waveBars.forEach(bar => bar.style.height = '8px');
}

function addStepLog(id, desc, state = 'done') {
    const item = document.createElement("div");
    item.className = `step-item ${state}`;
    item.innerHTML = `<span class="step-id">[${id}]</span> <span class="step-desc">${desc}</span>`;
    stepsFeed.appendChild(item);
    stepsFeed.scrollTop = stepsFeed.scrollHeight;
}

function runMockWorkflow() {
    statusEl.innerText = "STATUS: REASONING";
    transcriptEl.innerText = '"Find recent PDF in Downloads and prepare email summary."';
    stepsFeed.innerHTML = "";
    
    addStepLog("STEP 1", "Screen capture taken & active window identified", "running");
    
    setTimeout(() => {
        addStepLog("STEP 1", "Screen capture taken & parsed", "done");
        addStepLog("STEP 2", "Executing hotkey: Win + R -> shell:downloads", "running");
    }, 1000);

    setTimeout(() => {
        addStepLog("STEP 2", "Downloads directory launched", "done");
        addStepLog("STEP 3", "Targeting PDF element and extracting metrics", "running");
    }, 2200);

    setTimeout(() => {
        addStepLog("STEP 3", "Metrics extracted successfully", "done");
        addStepLog("FINISH", "Workflow complete. Audio feedback ready.", "done");
        statusEl.innerText = "STATUS: COMPLETED";
    }, 3500);
}
