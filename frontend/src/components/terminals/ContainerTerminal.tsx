import { useEffect, useRef, useState } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';

interface ContainerTerminalProps {
  vpsId: string;
  containerId: string;
}

export default function ContainerTerminal({ vpsId, containerId }: ContainerTerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal | null>(null);
  const fitAddon = useRef<FitAddon | null>(null);
  const websocket = useRef<WebSocket | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize terminal
    terminal.current = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
      theme: {
        background: '#0d1117',
        foreground: '#f0f6fc',
        cursor: '#f0f6fc',
        black: '#484f58',
        red: '#ff7b72',
        green: '#3fb950',
        yellow: '#d29922',
        blue: '#58a6ff',
        magenta: '#bc8cff',
        cyan: '#39c5cf',
        white: '#b1bac4',
        brightBlack: '#6e7681',
        brightRed: '#ffa198',
        brightGreen: '#56d364',
        brightYellow: '#e3b341',
        brightBlue: '#79c0ff',
        brightMagenta: '#d2a8ff',
        brightCyan: '#56d4dd',
        brightWhite: '#f0f6fc'
      },
      rows: 24,
      cols: 80
    });

    // Add addons
    fitAddon.current = new FitAddon();
    terminal.current.loadAddon(fitAddon.current);
    terminal.current.loadAddon(new WebLinksAddon());

    // Mount terminal
    terminal.current.open(terminalRef.current);
    fitAddon.current.fit();

    // Connect WebSocket
    connectWebSocket();

    // Handle window resize
    const handleResize = () => {
      if (fitAddon.current) {
        fitAddon.current.fit();
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (websocket.current) {
        websocket.current.close();
      }
      if (terminal.current) {
        terminal.current.dispose();
      }
    };
  }, [vpsId, containerId]);

  const connectWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8000/api/v1/vps/${vpsId}/container/${containerId}/terminal`;
    
    websocket.current = new WebSocket(wsUrl);

    websocket.current.onopen = () => {
      setConnectionStatus('connected');
      if (terminal.current) {
        terminal.current.clear();
        terminal.current.writeln('Connecting to container terminal...');
      }
    };

    websocket.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        switch (message.type) {
          case 'connected':
            if (terminal.current) {
              terminal.current.clear();
              terminal.current.writeln(`\r\n${message.message}\r\n`);
            }
            break;
          case 'output':
            if (terminal.current) {
              terminal.current.write(message.data);
            }
            break;
          case 'error':
            if (terminal.current) {
              terminal.current.writeln(`\r\nError: ${message.message}\r\n`);
            }
            setConnectionStatus('error');
            break;
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    websocket.current.onclose = () => {
      setConnectionStatus('disconnected');
      if (terminal.current) {
        terminal.current.writeln('\r\nConnection closed. Attempting to reconnect...\r\n');
      }
      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        if (connectionStatus !== 'connected') {
          connectWebSocket();
        }
      }, 3000);
    };

    websocket.current.onerror = () => {
      setConnectionStatus('error');
      if (terminal.current) {
        terminal.current.writeln('\r\nWebSocket connection error\r\n');
      }
    };

    // Handle terminal input
    if (terminal.current) {
      terminal.current.onData((data) => {
        if (websocket.current?.readyState === WebSocket.OPEN) {
          websocket.current.send(JSON.stringify({
            type: 'command',
            data: data
          }));
        }
      });
    }
  };

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'bg-green-500';
      case 'connecting':
        return 'bg-yellow-500';
      case 'disconnected':
        return 'bg-gray-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusText = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'disconnected':
        return 'Disconnected';
      case 'error':
        return 'Connection Error';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className="h-full bg-gray-900 flex flex-col">
      {/* Terminal Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <div className="flex space-x-1">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
            </div>
            <span className="text-gray-300 text-sm font-medium">Container Terminal</span>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <div className="text-gray-400 text-xs font-mono">{containerId.slice(0, 12)}</div>
          <div className={`w-2 h-2 rounded-full ${getStatusColor()}`}></div>
          <span className="text-gray-300 text-sm">{getStatusText()}</span>
        </div>
      </div>

      {/* Terminal Container */}
      <div className="flex-1 p-4 bg-gray-900">
        <div 
          ref={terminalRef} 
          className="h-full w-full rounded-md"
          style={{ backgroundColor: '#0d1117' }}
        />
      </div>

      {/* Connection Error Message */}
      {connectionStatus === 'error' && (
        <div className="bg-red-900 border-t border-red-700 px-4 py-2">
          <p className="text-red-200 text-sm">
            Unable to connect to container terminal. The container may not be running or may not have a shell available.
          </p>
        </div>
      )}
    </div>
  );
}