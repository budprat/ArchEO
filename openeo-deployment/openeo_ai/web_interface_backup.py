# ABOUTME: Web-based chat interface for OpenEO AI Assistant using WebSockets.
# Provides a browser-accessible UI for conversational Earth Observation analysis.

"""
OpenEO AI Web Interface

WebSocket-based chat interface accessible via browser.
Supports real-time streaming responses and visualization display.
"""

import asyncio
import json
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .sdk.client import OpenEOAIClient, OpenEOAIConfig, TOOL_DEFINITIONS
from .visualization.maps import MapComponent


app = FastAPI(title="OpenEO AI Assistant", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections and sessions
connections: Dict[str, WebSocket] = {}
sessions: Dict[str, dict] = {}


# HTML Frontend
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenEO AI Assistant</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e4e4e4;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 15px;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        header {
            text-align: center;
            padding: 15px 0;
            border-bottom: 1px solid #3a3a5c;
        }

        header h1 {
            color: #4ecdc4;
            font-size: 1.8em;
            margin-bottom: 3px;
        }

        header p {
            color: #888;
            font-size: 0.85em;
        }

        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            margin: 15px 0;
        }

        #messages {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            margin-bottom: 15px;
        }

        .message {
            margin-bottom: 14px;
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 90%;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            background: #4ecdc4;
            color: #1a1a2e;
            margin-left: auto;
            border-bottom-right-radius: 4px;
        }

        .message.assistant {
            background: #2a2a4a;
            border-bottom-left-radius: 4px;
        }

        .message.tool {
            background: #1e3a5f;
            border-left: 3px solid #4ecdc4;
            font-size: 0.9em;
        }

        .message.error {
            background: #5a2a2a;
            border-left: 3px solid #ff6b6b;
        }

        .message.visualization {
            background: #1a2a1a;
            border-left: 3px solid #4ecdc4;
            max-width: 100%;
        }

        /* Map Styles */
        .map-wrapper {
            margin-top: 10px;
            border-radius: 8px;
            overflow: hidden;
            background: #111;
        }

        .map-container {
            width: 100%;
            height: 450px;
        }

        .map-controls {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            padding: 12px;
            background: rgba(0,0,0,0.5);
            border-top: 1px solid #333;
        }

        .control-group {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .control-group label {
            font-size: 0.75em;
            color: #888;
            text-transform: uppercase;
        }

        .control-group input[type="range"] {
            width: 120px;
            accent-color: #4ecdc4;
        }

        .control-group select {
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid #444;
            background: #2a2a4a;
            color: #e4e4e4;
            font-size: 0.85em;
            cursor: pointer;
        }

        .control-group select:hover {
            border-color: #4ecdc4;
        }

        .map-btn {
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid #444;
            background: #2a2a4a;
            color: #e4e4e4;
            font-size: 0.85em;
            cursor: pointer;
            transition: all 0.2s;
        }

        .map-btn:hover {
            background: #4ecdc4;
            color: #1a1a2e;
            border-color: #4ecdc4;
        }

        .map-btn.active {
            background: #4ecdc4;
            color: #1a1a2e;
        }

        .map-info {
            display: flex;
            gap: 15px;
            padding: 8px 12px;
            background: rgba(0,0,0,0.3);
            font-size: 0.8em;
            color: #aaa;
        }

        .map-info span {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .colorbar {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: rgba(0,0,0,0.3);
        }

        .colorbar-gradient {
            width: 150px;
            height: 12px;
            border-radius: 3px;
        }

        .colorbar-labels {
            display: flex;
            justify-content: space-between;
            font-size: 0.75em;
            color: #aaa;
        }

        .message pre {
            background: rgba(0, 0, 0, 0.3);
            padding: 10px;
            border-radius: 6px;
            overflow-x: auto;
            margin-top: 8px;
            font-size: 0.85em;
            max-height: 200px;
        }

        .message code {
            background: rgba(0, 0, 0, 0.3);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }

        .tool-name {
            color: #4ecdc4;
            font-weight: bold;
            font-size: 0.85em;
            margin-bottom: 6px;
        }

        .input-container {
            display: flex;
            gap: 12px;
        }

        #messageInput {
            flex: 1;
            padding: 14px 18px;
            border: none;
            border-radius: 12px;
            background: #2a2a4a;
            color: #e4e4e4;
            font-size: 1em;
            outline: none;
            transition: box-shadow 0.3s;
        }

        #messageInput:focus {
            box-shadow: 0 0 0 2px #4ecdc4;
        }

        #messageInput::placeholder {
            color: #666;
        }

        .send-btn {
            padding: 14px 28px;
            background: #4ecdc4;
            color: #1a1a2e;
            border: none;
            border-radius: 12px;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }

        .send-btn:hover {
            background: #3dbdb5;
            transform: translateY(-2px);
        }

        .send-btn:disabled {
            background: #3a3a5c;
            color: #666;
            cursor: not-allowed;
            transform: none;
        }

        .status {
            text-align: center;
            padding: 6px;
            font-size: 0.8em;
            color: #888;
        }

        .status.connected {
            color: #4ecdc4;
        }

        .status.disconnected {
            color: #ff6b6b;
        }

        /* Collapsible Tools Panel */
        .tools-panel {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            margin-bottom: 15px;
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .tools-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            cursor: pointer;
            user-select: none;
        }

        .tools-header:hover {
            background: rgba(255,255,255,0.05);
        }

        .tools-header h3 {
            color: #4ecdc4;
            font-size: 0.9em;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .tools-toggle {
            color: #4ecdc4;
            font-size: 1.2em;
            transition: transform 0.3s;
        }

        .tools-panel.collapsed .tools-toggle {
            transform: rotate(-90deg);
        }

        .tools-panel.collapsed .tools-content {
            max-height: 0;
            padding: 0 16px;
            opacity: 0;
        }

        .tools-content {
            padding: 0 16px 16px;
            max-height: 500px;
            opacity: 1;
            transition: all 0.3s ease;
        }

        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 8px;
        }

        .tool-badge {
            background: #2a2a4a;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.75em;
            color: #aaa;
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
        }

        .tool-badge:hover {
            background: #3a3a5c;
            color: #4ecdc4;
            transform: translateY(-1px);
        }

        .tool-category {
            margin-bottom: 12px;
        }

        .tool-category-title {
            font-size: 0.7em;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 6px;
            padding-left: 4px;
        }

        .typing-indicator {
            display: none;
            padding: 12px 16px;
            background: #2a2a4a;
            border-radius: 12px;
            max-width: 80px;
        }

        .typing-indicator.active {
            display: block;
        }

        .typing-indicator span {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #4ecdc4;
            border-radius: 50%;
            margin: 0 2px;
            animation: bounce 1.4s infinite ease-in-out;
        }

        .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
        .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
        }

        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb {
            background: #4a4a6a;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #5a5a7a;
        }

        /* Leaflet overrides */
        .leaflet-control-zoom a {
            background: #2a2a4a !important;
            color: #4ecdc4 !important;
            border-color: #444 !important;
        }

        .leaflet-control-zoom a:hover {
            background: #4ecdc4 !important;
            color: #1a1a2e !important;
        }

        .leaflet-bar {
            border: none !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3) !important;
        }

        .custom-tooltip {
            background: rgba(0,0,0,0.8);
            border: 1px solid #4ecdc4;
            border-radius: 4px;
            padding: 4px 8px;
            color: #fff;
            font-size: 12px;
        }

        /* Chart styles */
        .chart-wrapper {
            margin-top: 10px;
            border-radius: 8px;
            overflow: hidden;
            background: #1a1a2e;
            padding: 15px;
        }

        .chart-container {
            position: relative;
            width: 100%;
            height: 300px;
        }

        .chart-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            padding: 12px;
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
            margin-top: 10px;
        }

        .chart-stat {
            display: flex;
            flex-direction: column;
            min-width: 80px;
        }

        .chart-stat-label {
            font-size: 0.7em;
            color: #888;
            text-transform: uppercase;
        }

        .chart-stat-value {
            font-size: 1.1em;
            color: #4ecdc4;
            font-weight: bold;
        }

        .chart-controls {
            display: flex;
            gap: 10px;
            padding: 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            margin-top: 10px;
        }

        .chart-btn {
            padding: 6px 12px;
            border-radius: 4px;
            border: 1px solid #444;
            background: #2a2a4a;
            color: #e4e4e4;
            font-size: 0.8em;
            cursor: pointer;
        }

        .chart-btn:hover {
            background: #4ecdc4;
            color: #1a1a2e;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌍 OpenEO AI Assistant</h1>
            <p>Earth Observation Analysis powered by Claude AI</p>
        </header>

        <div class="tools-panel" id="toolsPanel">
            <div class="tools-header" onclick="toggleTools()">
                <h3><span>🛠️</span> Available Tools</h3>
                <span class="tools-toggle">▼</span>
            </div>
            <div class="tools-content">
                <div class="tool-category">
                    <div class="tool-category-title">📊 Data Discovery</div>
                    <div class="tools-grid" id="dataTools"></div>
                </div>
                <div class="tool-category">
                    <div class="tool-category-title">⚙️ Processing</div>
                    <div class="tools-grid" id="processingTools"></div>
                </div>
                <div class="tool-category">
                    <div class="tool-category-title">🗺️ Visualization</div>
                    <div class="tools-grid" id="vizTools"></div>
                </div>
            </div>
        </div>

        <div class="chat-container">
            <div id="messages">
                <div class="message assistant">
                    <strong>Welcome!</strong> I'm your Earth Observation AI assistant. I can help you with:
                    <ul style="margin: 10px 0 0 20px;">
                        <li>Finding satellite data (Sentinel-2, Landsat, DEMs)</li>
                        <li>Creating NDVI and other vegetation indices</li>
                        <li>Managing batch processing jobs</li>
                        <li>Visualizing results on interactive maps</li>
                    </ul>
                    <p style="margin-top: 10px; color: #888;">Try: "Create an NDVI analysis for Delhi" or "Show available collections"</p>
                </div>
            </div>
            <div class="typing-indicator" id="typingIndicator">
                <span></span><span></span><span></span>
            </div>
        </div>

        <div class="input-container">
            <input type="text" id="messageInput" placeholder="Ask about Earth Observation data analysis..." autofocus>
            <button class="send-btn" id="sendBtn" onclick="sendMessage()">Send</button>
        </div>

        <div class="status" id="status">Connecting...</div>
    </div>

    <script>
        const tools = TOOLS_JSON_PLACEHOLDER;
        const COLORMAPS = {
            viridis: ['#440154', '#482777', '#3e4989', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6ece58', '#b5de2b', '#fde725'],
            plasma: ['#0d0887', '#5c01a6', '#9c179e', '#cc4778', '#ed7953', '#fdb42f', '#f0f921'],
            inferno: ['#000004', '#1b0c41', '#4a0c6b', '#781c6d', '#a52c60', '#cf4446', '#ed6925', '#fb9b06', '#f7d13d', '#fcffa4'],
            ndvi: ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
            terrain: ['#006147', '#107a2f', '#e8d77d', '#a14300', '#821e1e', '#a1a1a1', '#cecece', '#ffffff'],
            coolwarm: ['#3b4cc0', '#6788ee', '#9abbff', '#c9d7f0', '#edd1c2', '#f7a889', '#e26952', '#b40426'],
            grayscale: ['#000000', '#333333', '#666666', '#999999', '#cccccc', '#ffffff']
        };
        const BASEMAPS = {
            'OpenStreetMap': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            'CartoDB Dark': 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            'CartoDB Light': 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
            'ESRI Satellite': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            'ESRI Terrain': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}'
        };

        let ws;
        let sessionId = null;
        let messagesDiv, messageInput, sendBtn, statusDiv, typingIndicator;
        let activeMaps = {};
        let mapCounter = 0;

        document.addEventListener('DOMContentLoaded', function() {
            messagesDiv = document.getElementById('messages');
            messageInput = document.getElementById('messageInput');
            sendBtn = document.getElementById('sendBtn');
            statusDiv = document.getElementById('status');
            typingIndicator = document.getElementById('typingIndicator');

            // Categorize and populate tools
            const dataToolsGrid = document.getElementById('dataTools');
            const processingToolsGrid = document.getElementById('processingTools');
            const vizToolsGrid = document.getElementById('vizTools');

            tools.forEach(tool => {
                const badge = document.createElement('div');
                badge.className = 'tool-badge';
                const name = tool.name.replace('openeo_', '').replace('geoai_', '').replace('viz_', '');
                badge.textContent = name;
                badge.title = tool.description;
                badge.onclick = () => {
                    messageInput.value = `Use ${tool.name}: `;
                    messageInput.focus();
                };

                if (tool.name.includes('list') || tool.name.includes('get_collection')) {
                    dataToolsGrid.appendChild(badge);
                } else if (tool.name.includes('viz_') || tool.name.includes('show')) {
                    vizToolsGrid.appendChild(badge);
                } else {
                    processingToolsGrid.appendChild(badge);
                }
            });

            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') sendMessage();
            });

            connect();
        });

        function toggleTools() {
            document.getElementById('toolsPanel').classList.toggle('collapsed');
        }

        function connect() {
            const wsUrl = `ws://${window.location.hostname}:${window.location.port}/ws`;
            statusDiv.textContent = 'Connecting...';

            try {
                ws = new WebSocket(wsUrl);
            } catch (e) {
                statusDiv.textContent = 'Connection failed';
                return;
            }

            ws.onopen = () => {
                statusDiv.textContent = 'Connected';
                statusDiv.className = 'status connected';
                sendBtn.disabled = false;
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };

            ws.onclose = () => {
                statusDiv.textContent = 'Disconnected - Reconnecting...';
                statusDiv.className = 'status disconnected';
                sendBtn.disabled = true;
                setTimeout(connect, 3000);
            };

            ws.onerror = () => {
                statusDiv.textContent = 'Connection error';
                statusDiv.className = 'status disconnected';
            };
        }

        function handleMessage(data) {
            typingIndicator.classList.remove('active');

            switch (data.type) {
                case 'text':
                    addMessage(data.content, 'assistant');
                    break;
                case 'tool_result':
                    addToolResult(data.tool, data.result);
                    break;
                case 'tool_error':
                    addMessage(`Tool Error (${data.tool}): ${data.error}`, 'error');
                    break;
                case 'visualization':
                    addVisualization(data.content);
                    break;
                case 'session':
                    sessionId = data.session_id;
                    break;
                case 'error':
                    addMessage(`Error: ${data.content}`, 'error');
                    break;
            }
        }

        function addMessage(content, type) {
            const div = document.createElement('div');
            div.className = `message ${type}`;

            content = content
                .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                .replace(/\\*(.*?)\\*/g, '<em>$1</em>')
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                .split(String.fromCharCode(10)).join('<br>');

            div.innerHTML = content;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function addToolResult(toolName, result) {
            const div = document.createElement('div');
            div.className = 'message tool';

            const nameDiv = document.createElement('div');
            nameDiv.className = 'tool-name';
            nameDiv.textContent = `📦 ${toolName}`;
            div.appendChild(nameDiv);

            if (typeof result === 'object') {
                const pre = document.createElement('pre');
                const str = JSON.stringify(result, null, 2);
                pre.textContent = str.length > 800 ? str.substring(0, 800) + '\\n... (truncated)' : str;
                div.appendChild(pre);
            } else {
                div.innerHTML += result;
            }

            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function addVisualization(viz) {
            const div = document.createElement('div');
            div.className = 'message visualization';

            const title = viz.spec?.title || 'Visualization';
            div.innerHTML = `<strong>🗺️ ${title}</strong>`;

            if (viz.type === 'map' && viz.spec) {
                const mapId = 'map-' + (++mapCounter);
                const spec = viz.spec;

                // Create map wrapper with controls
                const wrapper = document.createElement('div');
                wrapper.className = 'map-wrapper';
                const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
                const sourcePath = spec.layers?.[0]?.source || spec.layers?.[0]?.path || '';
                wrapper.innerHTML = `
                    <div id="${mapId}" class="map-container"></div>
                    <div class="map-info">
                        <span>📍 Coords: <span id="${mapId}-coords">--</span></span>
                        <span>🔍 Zoom: <span id="${mapId}-zoom">${spec.zoom || 10}</span></span>
                        <span>📐 Bounds: ${spec.layers?.[0]?.bounds ? formatBounds(spec.layers[0].bounds) : '--'}</span>
                        <span>🕐 ${timestamp}</span>
                    </div>
                    <input type="hidden" id="${mapId}-source" value="${sourcePath}">
                    <div class="colorbar" id="${mapId}-colorbar">
                        <span style="font-size:0.75em;color:#888;">Value:</span>
                        <span id="${mapId}-min" style="font-size:0.8em;">${spec.colorbar?.min?.toFixed(3) || '0'}</span>
                        <div class="colorbar-gradient" id="${mapId}-gradient" style="background: linear-gradient(to right, ${getGradientCSS('ndvi')});"></div>
                        <span id="${mapId}-max" style="font-size:0.8em;">${spec.colorbar?.max?.toFixed(3) || '1'}</span>
                    </div>
                    <div class="map-controls">
                        <div class="control-group">
                            <label>Opacity</label>
                            <input type="range" id="${mapId}-opacity" min="0" max="100" value="80" oninput="updateMapOpacity('${mapId}', this.value)">
                        </div>
                        <div class="control-group">
                            <label>Colormap</label>
                            <select id="${mapId}-colormap" onchange="updateMapColormap('${mapId}', this.value)">
                                <option value="ndvi">NDVI</option>
                                <option value="viridis">Viridis</option>
                                <option value="plasma">Plasma</option>
                                <option value="inferno">Inferno</option>
                                <option value="coolwarm">Cool-Warm</option>
                                <option value="terrain">Terrain</option>
                                <option value="grayscale">Grayscale</option>
                            </select>
                        </div>
                        <div class="control-group">
                            <label>Basemap</label>
                            <select id="${mapId}-basemap" onchange="updateMapBasemap('${mapId}', this.value)">
                                <option value="CartoDB Dark">CartoDB Dark</option>
                                <option value="OpenStreetMap">OpenStreetMap</option>
                                <option value="CartoDB Light">CartoDB Light</option>
                                <option value="ESRI Satellite">ESRI Satellite</option>
                                <option value="ESRI Terrain">ESRI Terrain</option>
                            </select>
                        </div>
                        <div class="control-group" style="justify-content: flex-end;">
                            <label>&nbsp;</label>
                            <div style="display:flex;gap:6px;">
                                <button class="map-btn" onclick="toggleLayer('${mapId}')" id="${mapId}-toggle" title="Toggle Layer">👁️</button>
                                <button class="map-btn" onclick="fitMapBounds('${mapId}')" title="Fit Bounds">⬜</button>
                                <button class="map-btn" onclick="downloadMap('${mapId}')" title="Download">💾</button>
                                <button class="map-btn" onclick="toggleFullscreen('${mapId}')" title="Fullscreen">⛶</button>
                            </div>
                        </div>
                    </div>
                `;
                div.appendChild(wrapper);
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                // Initialize map
                setTimeout(() => initializeMap(mapId, spec), 100);
            } else if (viz.type === 'chart' && viz.spec) {
                const chartId = 'chart-' + (++mapCounter);
                const spec = viz.spec;

                div.innerHTML = `<strong>📊 ${spec.title || 'Chart'}</strong>`;

                const wrapper = document.createElement('div');
                wrapper.className = 'chart-wrapper';
                wrapper.innerHTML = `
                    <div class="chart-container">
                        <canvas id="${chartId}"></canvas>
                    </div>
                    ${spec.statistics ? `
                    <div class="chart-stats">
                        <div class="chart-stat"><span class="chart-stat-label">Min</span><span class="chart-stat-value">${spec.statistics.min?.toFixed(3) || '--'}</span></div>
                        <div class="chart-stat"><span class="chart-stat-label">Max</span><span class="chart-stat-value">${spec.statistics.max?.toFixed(3) || '--'}</span></div>
                        <div class="chart-stat"><span class="chart-stat-label">Mean</span><span class="chart-stat-value">${spec.statistics.mean?.toFixed(3) || '--'}</span></div>
                        <div class="chart-stat"><span class="chart-stat-label">Std</span><span class="chart-stat-value">${spec.statistics.std?.toFixed(3) || '--'}</span></div>
                        <div class="chart-stat"><span class="chart-stat-label">Count</span><span class="chart-stat-value">${spec.statistics.count || '--'}</span></div>
                    </div>
                    ` : ''}
                    <div class="chart-controls">
                        <button class="chart-btn" onclick="downloadChart('${chartId}')" title="Download PNG">💾 Download</button>
                    </div>
                `;
                div.appendChild(wrapper);
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                // Initialize chart
                setTimeout(() => initializeChart(chartId, spec), 100);
            } else if (viz.type === 'comparison_slider' && viz.spec) {
                const compId = 'comp-' + (++mapCounter);
                const spec = viz.spec;

                div.innerHTML = `<strong>🔄 ${spec.title || 'Comparison'}</strong>`;

                const wrapper = document.createElement('div');
                wrapper.className = 'map-wrapper';
                wrapper.innerHTML = `
                    <div id="${compId}" class="map-container" style="height: 400px;"></div>
                    <div class="map-info">
                        <span>📍 Coords: <span id="${compId}-coords">--</span></span>
                        <span>🔍 Zoom: <span id="${compId}-zoom">${spec.zoom || 10}</span></span>
                    </div>
                    <div class="map-controls">
                        <div class="control-group" style="flex: 1;">
                            <label>Slide Position</label>
                            <input type="range" id="${compId}-slider" min="0" max="100" value="50" style="width: 100%;" oninput="updateComparisonSlider('${compId}', this.value)">
                        </div>
                        <div class="control-group">
                            <label>&nbsp;</label>
                            <div style="display:flex;gap:6px;">
                                <button class="map-btn" onclick="fitMapBounds('${compId}')" title="Fit Bounds">⬜</button>
                                <button class="map-btn" onclick="toggleFullscreen('${compId}')" title="Fullscreen">⛶</button>
                            </div>
                        </div>
                    </div>
                `;
                div.appendChild(wrapper);
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                // Initialize comparison slider
                setTimeout(() => initializeComparison(compId, spec), 100);
            } else if (viz.type === 'quality_dashboard' && viz.spec) {
                const spec = viz.spec;
                const gradeColors = {
                    'A': '#4CAF50', 'B': '#8BC34A', 'C': '#FFC107',
                    'D': '#FF9800', 'F': '#F44336'
                };
                const gradeColor = gradeColors[spec.grade] || '#9E9E9E';

                // Build cloud and temporal sections
                let cloudSection = '';
                let temporalSection = '';
                let recsSection = '';

                if (spec.sections) {
                    for (const section of spec.sections) {
                        if (section.type === 'metric' && section.title === 'Cloud Coverage') {
                            const c = section.content;
                            cloudSection = `
                                <div style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 15px;">
                                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                                        <span style="font-size: 20px;">☁️</span>
                                        <span style="color: #aaa; font-size: 14px;">Cloud Coverage</span>
                                    </div>
                                    <div style="font-size: 28px; font-weight: bold; color: ${c.color};">
                                        ${c.value}${c.unit}
                                    </div>
                                    <div style="color: #888; font-size: 12px; margin-top: 5px;">
                                        ${c.details.join(' | ')}
                                    </div>
                                    ${c.warnings.length ? '<div style="color: #FF9800; font-size: 11px; margin-top: 5px;">⚠️ ' + c.warnings.join(', ') + '</div>' : ''}
                                </div>`;
                        }
                        if (section.type === 'metric' && section.title === 'Temporal Coverage') {
                            const c = section.content;
                            temporalSection = `
                                <div style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 15px;">
                                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                                        <span style="font-size: 20px;">📅</span>
                                        <span style="color: #aaa; font-size: 14px;">Temporal Coverage</span>
                                    </div>
                                    <div style="font-size: 28px; font-weight: bold; color: ${c.color};">
                                        ${c.value}${c.unit}
                                    </div>
                                    <div style="color: #888; font-size: 12px; margin-top: 5px;">
                                        ${c.details.join(' | ')}
                                    </div>
                                    ${c.warnings.length ? '<div style="color: #FF9800; font-size: 11px; margin-top: 5px;">⚠️ ' + c.warnings.join(', ') + '</div>' : ''}
                                </div>`;
                        }
                        if (section.type === 'recommendations') {
                            const items = section.content.items.map(i => '<li style="margin: 4px 0;">' + i.text + '</li>').join('');
                            recsSection = `
                                <div style="margin-top: 15px; padding: 15px; background: rgba(33,150,243,0.1); border-radius: 8px; border-left: 3px solid #2196F3;">
                                    <div style="color: #2196F3; font-weight: bold; margin-bottom: 8px;">💡 Recommendations</div>
                                    <ul style="margin: 0; padding-left: 20px; color: #ccc;">${items}</ul>
                                </div>`;
                        }
                    }
                }

                div.innerHTML = `
                    <div class="quality-dashboard" style="
                        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d3d 100%);
                        border-radius: 12px;
                        padding: 20px;
                        margin: 10px 0;
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                            <h3 style="margin: 0; color: #fff;">📊 ${spec.title || 'Data Quality Assessment'}</h3>
                            <div style="
                                background: ${gradeColor};
                                color: white;
                                padding: 8px 16px;
                                border-radius: 20px;
                                font-weight: bold;
                                font-size: 18px;
                            ">Grade: ${spec.grade} (${spec.score}%)</div>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                            ${cloudSection}
                            ${temporalSection}
                        </div>
                        ${recsSection}
                    </div>`;
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } else {
                if (viz.spec) {
                    const pre = document.createElement('pre');
                    pre.textContent = JSON.stringify(viz.spec, null, 2).substring(0, 500);
                    div.appendChild(pre);
                }
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }

        function initializeMap(mapId, spec) {
            const map = L.map(mapId, {
                zoomControl: true,
                attributionControl: false
            }).setView(spec.center || [0, 0], spec.zoom || 10);

            // Add basemap
            const basemapLayer = L.tileLayer(BASEMAPS['CartoDB Dark'], {
                maxZoom: 19
            }).addTo(map);

            // Store map data
            activeMaps[mapId] = {
                map: map,
                basemapLayer: basemapLayer,
                imageLayer: null,
                imageData: null,
                bounds: null,
                spec: spec,
                visible: true,
                sourcePath: null,
                vmin: spec.colorbar?.min,
                vmax: spec.colorbar?.max
            };

            // Add raster layer
            if (spec.layers && spec.layers.length > 0) {
                const layer = spec.layers[0];
                if (layer.type === 'raster' && layer.url && layer.bounds) {
                    activeMaps[mapId].imageData = layer.url;
                    activeMaps[mapId].bounds = layer.bounds;
                    // Store source path for re-rendering with different colormaps
                    activeMaps[mapId].sourcePath = layer.source || layer.path || document.getElementById(`${mapId}-source`)?.value || null;
                    activeMaps[mapId].vmin = layer.vmin ?? spec.colorbar?.min;
                    activeMaps[mapId].vmax = layer.vmax ?? spec.colorbar?.max;

                    const imageLayer = L.imageOverlay(layer.url, layer.bounds, {
                        opacity: layer.opacity || 0.8
                    }).addTo(map);

                    activeMaps[mapId].imageLayer = imageLayer;
                    map.fitBounds(layer.bounds);
                }
            }

            // Update coordinates on mouse move
            map.on('mousemove', (e) => {
                document.getElementById(`${mapId}-coords`).textContent =
                    `${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`;
            });

            // Update zoom display
            map.on('zoomend', () => {
                document.getElementById(`${mapId}-zoom`).textContent = map.getZoom();
            });
        }

        function updateMapOpacity(mapId, value) {
            if (activeMaps[mapId]?.imageLayer) {
                activeMaps[mapId].imageLayer.setOpacity(value / 100);
            }
        }

        async function updateMapColormap(mapId, colormap) {
            const gradient = document.getElementById(`${mapId}-gradient`);
            if (gradient) {
                gradient.style.background = `linear-gradient(to right, ${getGradientCSS(colormap)})`;
            }

            // Get source path and re-render with new colormap
            const mapData = activeMaps[mapId];
            if (!mapData) return;

            const sourcePath = mapData.sourcePath;
            if (!sourcePath) {
                console.log('No source path available for colormap change');
                return;
            }

            // Show loading indicator
            const select = document.getElementById(`${mapId}-colormap`);
            if (select) select.disabled = true;

            try {
                const params = new URLSearchParams({
                    path: sourcePath,
                    colormap: colormap
                });
                if (mapData.vmin !== undefined) params.append('vmin', mapData.vmin);
                if (mapData.vmax !== undefined) params.append('vmax', mapData.vmax);

                const response = await fetch(`/render-raster?${params}`);
                const result = await response.json();

                if (result.url && mapData.imageLayer) {
                    // Update image layer with new colormap
                    const bounds = mapData.bounds;
                    mapData.map.removeLayer(mapData.imageLayer);

                    const newLayer = L.imageOverlay(result.url, bounds, {
                        opacity: mapData.imageLayer.options.opacity || 0.8
                    });
                    newLayer.addTo(mapData.map);
                    mapData.imageLayer = newLayer;
                    mapData.imageData = result.url;

                    // Update colorbar values
                    if (result.vmin !== undefined) {
                        document.getElementById(`${mapId}-min`).textContent = result.vmin.toFixed(3);
                        mapData.vmin = result.vmin;
                    }
                    if (result.vmax !== undefined) {
                        document.getElementById(`${mapId}-max`).textContent = result.vmax.toFixed(3);
                        mapData.vmax = result.vmax;
                    }

                    console.log(`Colormap updated to ${colormap}`);
                } else if (result.error) {
                    console.error('Colormap error:', result.error);
                }
            } catch (err) {
                console.error('Failed to update colormap:', err);
            } finally {
                if (select) select.disabled = false;
            }
        }

        function updateMapBasemap(mapId, basemapName) {
            if (activeMaps[mapId]) {
                const data = activeMaps[mapId];
                data.map.removeLayer(data.basemapLayer);
                data.basemapLayer = L.tileLayer(BASEMAPS[basemapName], { maxZoom: 19 }).addTo(data.map);
                if (data.imageLayer) {
                    data.imageLayer.bringToFront();
                }
            }
        }

        function toggleLayer(mapId) {
            if (activeMaps[mapId]) {
                const data = activeMaps[mapId];
                const btn = document.getElementById(`${mapId}-toggle`);
                if (data.visible) {
                    data.map.removeLayer(data.imageLayer);
                    data.visible = false;
                    btn.style.opacity = '0.5';
                } else {
                    data.imageLayer.addTo(data.map);
                    data.visible = true;
                    btn.style.opacity = '1';
                }
            }
        }

        function fitMapBounds(mapId) {
            if (activeMaps[mapId]?.bounds) {
                activeMaps[mapId].map.fitBounds(activeMaps[mapId].bounds);
            }
        }

        function downloadMap(mapId) {
            if (activeMaps[mapId]?.imageData) {
                const link = document.createElement('a');
                link.href = activeMaps[mapId].imageData;
                link.download = `map-${mapId}.png`;
                link.click();
            }
        }

        function toggleFullscreen(mapId) {
            const container = document.getElementById(mapId);
            if (!document.fullscreenElement) {
                container.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        }

        function getGradientCSS(colormap) {
            const colors = COLORMAPS[colormap] || COLORMAPS.viridis;
            return colors.join(', ');
        }

        function formatBounds(bounds) {
            if (!bounds || bounds.length < 2) return '--';
            return `[${bounds[0][0].toFixed(2)}, ${bounds[0][1].toFixed(2)}] to [${bounds[1][0].toFixed(2)}, ${bounds[1][1].toFixed(2)}]`;
        }

        // Chart functions
        let activeCharts = {};

        function initializeChart(chartId, spec) {
            const ctx = document.getElementById(chartId);
            if (!ctx) return;

            const chartType = spec.chart_type || 'line';
            const data = spec.data || {};

            let chartConfig = {
                type: chartType === 'histogram' ? 'bar' : chartType,
                data: {
                    labels: data.x || [],
                    datasets: []
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#e4e4e4' }
                        },
                        title: {
                            display: false
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            title: {
                                display: true,
                                text: spec.xaxis?.title || '',
                                color: '#888'
                            }
                        },
                        y: {
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            title: {
                                display: true,
                                text: spec.yaxis?.title || '',
                                color: '#888'
                            }
                        }
                    }
                }
            };

            // Handle different chart types
            if (chartType === 'line') {
                if (data.series) {
                    chartConfig.data.datasets = data.series;
                } else {
                    chartConfig.data.datasets = [{
                        label: data.series_name || 'Value',
                        data: data.y || [],
                        borderColor: spec.style?.color || '#4ecdc4',
                        backgroundColor: (spec.style?.color || '#4ecdc4') + '33',
                        fill: spec.style?.fill !== false,
                        tension: 0.1
                    }];
                }

                // Handle time axis
                if (spec.xaxis?.type === 'time') {
                    chartConfig.options.scales.x.type = 'time';
                    chartConfig.options.scales.x.time = {
                        displayFormats: { day: 'MMM d' }
                    };
                }
            } else if (chartType === 'bar' || chartType === 'histogram') {
                chartConfig.data.datasets = [{
                    label: 'Value',
                    data: data.y || [],
                    backgroundColor: spec.style?.color || '#2196F3',
                    borderColor: spec.style?.color || '#2196F3',
                    borderWidth: 1
                }];
            } else if (chartType === 'pie') {
                chartConfig.data.labels = data.labels || [];
                chartConfig.data.datasets = [{
                    data: data.values || [],
                    backgroundColor: spec.style?.colors || [
                        '#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0'
                    ]
                }];
                delete chartConfig.options.scales;
            } else if (chartType === 'scatter') {
                const points = [];
                for (let i = 0; i < (data.x || []).length; i++) {
                    points.push({ x: data.x[i], y: data.y[i] });
                }
                chartConfig.data.datasets = [{
                    label: 'Data',
                    data: points,
                    backgroundColor: spec.style?.color || '#FF5722'
                }];
                chartConfig.data.labels = undefined;
            }

            const chart = new Chart(ctx, chartConfig);
            activeCharts[chartId] = chart;
        }

        function downloadChart(chartId) {
            const chart = activeCharts[chartId];
            if (chart) {
                const link = document.createElement('a');
                link.href = chart.toBase64Image();
                link.download = `chart-${chartId}.png`;
                link.click();
            }
        }

        // Comparison slider functions
        function initializeComparison(compId, spec) {
            const map = L.map(compId, {
                zoomControl: true,
                attributionControl: false
            }).setView(spec.center || [0, 0], spec.zoom || 10);

            // Add basemap
            L.tileLayer(BASEMAPS['CartoDB Dark'], { maxZoom: 19 }).addTo(map);

            // Create container for side-by-side
            const container = document.getElementById(compId);
            const beforeDiv = document.createElement('div');
            const afterDiv = document.createElement('div');

            beforeDiv.style.cssText = 'position: absolute; top: 0; left: 0; width: 50%; height: 100%; overflow: hidden; z-index: 400; pointer-events: none;';
            afterDiv.style.cssText = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 399; pointer-events: none;';

            container.style.position = 'relative';
            container.appendChild(afterDiv);
            container.appendChild(beforeDiv);

            // Add images
            let beforeLayer = null;
            let afterLayer = null;

            if (spec.before?.url && spec.before?.bounds) {
                beforeLayer = L.imageOverlay(spec.before.url, spec.before.bounds, { opacity: 0.9 });
                beforeLayer.addTo(map);
            }

            if (spec.after?.url && spec.after?.bounds) {
                afterLayer = L.imageOverlay(spec.after.url, spec.after.bounds, { opacity: 0.9 });
                afterLayer.addTo(map);
            }

            // Fit bounds
            if (spec.before?.bounds) {
                map.fitBounds(spec.before.bounds);
            }

            // Store for slider control
            activeMaps[compId] = {
                map: map,
                beforeLayer: beforeLayer,
                afterLayer: afterLayer,
                beforeDiv: beforeDiv,
                bounds: spec.before?.bounds || spec.after?.bounds
            };

            // Update coordinates
            map.on('mousemove', (e) => {
                const coordsEl = document.getElementById(`${compId}-coords`);
                if (coordsEl) {
                    coordsEl.textContent = `${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`;
                }
            });

            map.on('zoomend', () => {
                const zoomEl = document.getElementById(`${compId}-zoom`);
                if (zoomEl) {
                    zoomEl.textContent = map.getZoom();
                }
            });
        }

        function updateComparisonSlider(compId, value) {
            const data = activeMaps[compId];
            if (data && data.beforeDiv) {
                data.beforeDiv.style.width = value + '%';
            }
        }

        function sendMessage() {
            const message = messageInput.value.trim();
            if (!message || ws.readyState !== WebSocket.OPEN) return;

            addMessage(message, 'user');

            ws.send(JSON.stringify({
                type: 'message',
                content: message,
                session_id: sessionId
            }));

            messageInput.value = '';
            typingIndicator.classList.add('active');
        }
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    """Serve the frontend HTML."""
    tools_json = json.dumps([{"name": t["name"], "description": t["description"][:100]} for t in TOOL_DEFINITIONS])
    html = HTML_TEMPLATE.replace("TOOLS_JSON_PLACEHOLDER", tools_json)
    return HTMLResponse(content=html)


@app.get("/render-raster")
async def render_raster(
    path: str = Query(..., description="Path to GeoTIFF file"),
    colormap: str = Query("viridis", description="Colormap name"),
    vmin: Optional[float] = Query(None, description="Min value"),
    vmax: Optional[float] = Query(None, description="Max value")
):
    """Re-render a raster with a specified colormap."""
    import base64
    import numpy as np

    try:
        component = MapComponent()
        data, metadata = component._load_raster(path)

        # Calculate bounds if not provided
        calc_vmin = vmin if vmin is not None else float(np.nanmin(data))
        calc_vmax = vmax if vmax is not None else float(np.nanmax(data))

        # Apply colormap
        colored_image = component._apply_colormap(data, colormap, calc_vmin, calc_vmax)

        # Encode to PNG
        image_b64 = component._encode_image(colored_image)

        return {
            "url": f"data:image/png;base64,{image_b64}",
            "colormap": colormap,
            "vmin": calc_vmin,
            "vmax": calc_vmax
        }
    except Exception as e:
        return {"error": str(e)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for chat."""
    await websocket.accept()
    print(f"[WS] New connection accepted")

    connection_id = str(uuid.uuid4())
    connections[connection_id] = websocket
    user_id = f"web_user_{connection_id[:8]}"

    # Initialize client
    config = OpenEOAIConfig()
    client = OpenEOAIClient(config=config)
    print(f"[WS] Client initialized for user {user_id}")

    session_id = None

    try:
        while True:
            data = await websocket.receive_json()
            print(f"[WS] Received: {data}")

            if data.get("type") == "message":
                content = data.get("content", "")
                session_id = data.get("session_id") or session_id
                print(f"[WS] Processing message: {content[:50]}...")

                try:
                    async for response in client.chat(
                        content,
                        user_id=user_id,
                        session_id=session_id
                    ):
                        print(f"[WS] Sending response: {response.get('type')}")
                        await websocket.send_json(response)

                        if response.get("type") == "session":
                            session_id = response.get("session_id")

                except Exception as e:
                    print(f"[WS] Error: {e}")
                    import traceback
                    traceback.print_exc()
                    await websocket.send_json({
                        "type": "error",
                        "content": str(e)
                    })

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {connection_id}")
    except Exception as e:
        print(f"[WS] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if connection_id in connections:
            del connections[connection_id]


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the web server."""
    print(f"\n{'='*60}")
    print("OpenEO AI Web Interface")
    print(f"{'='*60}")
    print(f"\n🌍 Open your browser at: http://localhost:{port}")
    print(f"\nAvailable tools: {len(TOOL_DEFINITIONS)}")
    for tool in TOOL_DEFINITIONS:
        print(f"  • {tool['name']}")
    print(f"\n{'='*60}\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenEO AI Web Interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)
