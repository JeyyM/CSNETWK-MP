# LSNP - Lightweight Social Networking Protocol

A decentralized communication framework designed for local area networks where internet connectivity is limited or unavailable. This Python implementation of LSNP enables peer-to-peer social networking within LANs using simple plaintext messaging over UDP, making it perfect for educational institutions, rural communities, disaster zones, or any environment where traditional social networking infrastructure isn't accessible.

## Overview

LSNP (Lightweight Social Networking Protocol) is built to work in disconnected or resource-constrained environments. Whether you're in a classroom without internet, a remote location, or dealing with network outages, LSNP lets you create an instant social network using only local WiFi or ethernet connections.

### Why LSNP?

**Designed for Real-World Constraints**
- Works without internet connectivity or centralized servers
- Operates efficiently on minimal hardware and network resources
- Perfect for educational settings, emergency situations, or remote areas
- Quick deployment with no infrastructure setup required

**Simple Yet Powerful**
- Human-readable plaintext protocol that's easy to debug and extend
- UDP-based communication for low latency and minimal overhead
- Automatic peer discovery - just start the app and find others instantly
- Modular design that can be adapted for different use cases

### What You Can Do

- **Connect instantly** with anyone on your local network
- **Send messages** privately or in groups without any servers
- **Share files** directly between devices
- **Play games** like Tic-Tac-Toe with real-time synchronization
- **Post updates** and see what others are sharing
- **Stay connected** even when the internet goes down

LSNP transforms any local network into a social platform, bringing people together through technology that works anywhere, anytime.

## Features

### 🌐 Peer Discovery & Management
- **Automatic peer discovery** on local network
- **Real-time presence tracking** with ping/heartbeat system
- **User profiles** with customizable display names and status messages
- **Peer list management** with active/inactive status indicators

### 💬 Messaging System
- **Direct messaging** between any two users
- **Group messaging** with create/join functionality
- **Social media posts** with timeline feeds
- **Message persistence** and conversation history
- **Real-time message delivery** with acknowledgment system

### 📁 File Sharing
- **Peer-to-peer file transfer** with no size limitations
- **File offer/accept mechanism** for secure transfers
- **Progress tracking** during file transfers
- **Multiple concurrent transfers** supported

### 🎮 Interactive Games
- **Tic-Tac-Toe multiplayer** with real-time gameplay
- **Game invitations** and matchmaking
- **Turn-based mechanics** with move validation
- **Game state synchronization** across peers

### 👥 Group Management
- **Create and manage groups** with member control
- **Role-based permissions** (creator vs. member privileges)
- **Group messaging** with broadcast capabilities
- **Member invitation system**

### 🔒 Security & Authentication
- **Token-based authentication** for message validation
- **Scope-based authorization** (broadcast, chat, presence, file, game)
- **Message integrity verification**
- **Automatic token expiration** and renewal

### 🛠️ Technical Features
- **UDP-based communication** for low latency
- **Message deduplication** to prevent spam
- **Verbose logging mode** for debugging
- **Graceful connection handling** with automatic cleanup
- **Cross-platform compatibility** (Windows, Linux, macOS)

## Screenshots

### Main Menu
*The central hub showing all available features and options*

### Peer Discovery
*Real-time view of active users on the local network*

### Direct Messaging
*Private conversations between users with message history*

### Group Chat
*Multi-user group conversations with member management*

### File Sharing
*File transfer interface with progress tracking*

### Tic-Tac-Toe Game
*Interactive multiplayer game with real-time synchronization*

*Note: Add actual screenshots here showing the terminal-based interface in action*

## Prerequisites

- **Python 3.7+** - Required for running the application
- **Local Area Network** - All users must be on the same network subnet
- **Firewall Configuration** - UDP port 50999 must be open for communication
- **Administrator Privileges** - Required on Windows for firewall rule creation

### Network Requirements
- All devices must be on the same subnet (e.g., 192.168.1.x)
- UDP broadcast packets must be allowed on the network
- Port 50999 must be available and not blocked by firewalls

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/JeyyM/CSNETWK-MP.git
   cd CSNETWK-MP
   ```

2. **Verify Python installation**
   ```bash
   python --version
   # Should show Python 3.7 or higher
   ```

3. **No additional dependencies required** - The application uses only Python standard library modules

## Network Setup

### Windows (PowerShell as Administrator)
```powershell
# Create firewall rule to allow LSNP traffic
New-NetFirewallRule -DisplayName "LSNP UDP 50999" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 50999

# To remove the rule when done (for security)
Remove-NetFirewallRule -DisplayName "LSNP UDP 50999"
```

### Linux/macOS
```bash
# Check if port 50999 is available
netstat -ul | grep 50999

# If using ufw (Ubuntu/Debian)
sudo ufw allow 50999/udp

# If using firewalld (CentOS/RHEL)
sudo firewall-cmd --add-port=50999/udp --permanent
sudo firewall-cmd --reload
```

## Usage

### Starting the Application
```bash
python main.py
```

### First-Time Setup
1. Enter your **username** (will be used as your identifier)
2. Enter your **display name** (shown to other users)
3. Set your **status message** (optional)
4. Choose **verbose mode** (recommended for debugging)

### Main Menu Options
- **0** - Toggle verbose logging on/off
- **1** - View discovered peers and their profiles
- **2** - Access posts feed (view/create social posts)
- **3** - Send direct messages to other users
- **4** - Create/join groups and send group messages
- **5** - Share files with other users
- **6** - Play Tic-Tac-Toe with other users
- **7** - View and edit your profile
- **8** - Exit the application

### Basic Workflow
1. **Start the application** and complete initial setup
2. **Wait for peer discovery** (other users will appear automatically)
3. **Begin interacting** through messaging, file sharing, or games
4. **Use verbose mode** to see network activity and debugging information

## Architecture

LSNP follows a decentralized peer-to-peer architecture with the following components:

### Core Components
- **NetworkManager** - Handles UDP communication and message routing
- **UDPListener** - Listens for incoming messages on port 50999
- **MessageRouter** - Routes incoming messages to appropriate handlers
- **Application State** - Maintains peer lists, conversations, and game states

### Service Layer
- **UserService** - Manages peer discovery and profile broadcasting
- **MessageService** - Handles direct messages and posts
- **GroupService** - Manages group creation and messaging
- **GameService** - Coordinates multiplayer Tic-Tac-Toe games
- **FileService** - Handles peer-to-peer file transfers
- **PingService** - Maintains peer presence and heartbeat

### User Interface
- **Terminal-based menus** for all user interactions
- **Real-time updates** for messages and game states
- **Verbose logging** for network debugging

### Data Flow
1. **Outgoing**: UI → Service → NetworkManager → UDP Broadcast/Unicast
2. **Incoming**: UDP Listener → MessageRouter → Handler → Service → UI Update

## Protocol

LSNP uses a custom text-based protocol over UDP with the following message format:

### Message Structure
```
TYPE: [MESSAGE_TYPE]
USER_ID: [username@ip_address]
FIELD_NAME: [field_value]
...

[Optional message body]
```

### Message Types
- **PROFILE** - User profile broadcasts for peer discovery
- **PING/PONG** - Heartbeat messages for presence tracking
- **POST** - Social media posts
- **CHAT** - Direct messages between users
- **GROUP_CHAT** - Group messaging
- **GAME_INVITE** - Tic-Tac-Toe game invitations
- **GAME_MOVE** - Game move updates
- **FILE_OFFER** - File sharing offers
- **FILE_ACCEPT** - File transfer acceptance
- **ACK** - Message acknowledgments
- **REVOKE** - Token revocation for logout

### Authentication
- **Token-based security** with scope validation
- **Automatic token generation** for different message types
- **Token expiration** and renewal mechanisms
- **Scope verification** (broadcast, chat, presence, file, game)

## File Structure

```
CSNETWK-MP/
├── main.py                 # Application entry point
├── src/
│   ├── app.py             # Main application controller
│   ├── core/
│   │   └── state.py       # Global application state management
│   ├── handlers/          # Message type handlers
│   │   ├── dm_handler.py
│   │   ├── file_handler.py
│   │   ├── game_handler.py
│   │   ├── group_handler.py
│   │   ├── like_handler.py
│   │   ├── message_router.py
│   │   ├── ping_handler.py
│   │   ├── post_handler.py
│   │   └── profile_handler.py
│   ├── models/            # Data models
│   │   ├── game.py        # Tic-Tac-Toe game models
│   │   ├── group.py       # Group and group message models
│   │   └── user.py        # User, peer, and message models
│   ├── network/           # Network communication layer
│   │   ├── client.py      # Network manager and utilities
│   │   ├── listener.py    # UDP message listener
│   │   └── protocol.py    # Message parsing and building
│   ├── services/          # Business logic services
│   │   ├── file_service.py
│   │   ├── game_service.py
│   │   ├── group_service.py
│   │   ├── message_service.py
│   │   ├── ping_service.py
│   │   └── user_service.py
│   ├── ui/                # User interface components
│   │   ├── components.py  # Shared UI utilities
│   │   ├── dm_menu.py     # Direct messaging interface
│   │   ├── file_menu.py   # File sharing interface
│   │   ├── game_menu.py   # Tic-Tac-Toe game interface
│   │   ├── group_menu.py  # Group messaging interface
│   │   ├── main_menu.py   # Main application menu
│   │   ├── peer_menu.py   # Peer discovery interface
│   │   └── posts_menu.py  # Social posts interface
│   └── utils/             # Utility functions
│       ├── auth.py        # Authentication and token management
│       ├── dedupe.py      # Message deduplication
│       └── setup.py       # Initial user setup
└── IMPORTANT.txt          # Firewall setup instructions
```

## Development

### Adding New Features
1. **Create models** in `src/models/` for new data structures
2. **Implement services** in `src/services/` for business logic
3. **Add message handlers** in `src/handlers/` for new message types
4. **Create UI components** in `src/ui/` for user interaction
5. **Update protocol** in `src/network/protocol.py` if needed

### Code Style
- Follow **PEP 8** Python style guidelines
- Use **type hints** for all function parameters and returns
- Add **docstrings** for all classes and public methods
- Implement **error handling** with appropriate try/catch blocks

### Testing
- Test on **multiple devices** on the same network
- Verify **firewall rules** are properly configured
- Test **concurrent users** and message handling
- Validate **file transfers** of various sizes
- Test **game synchronization** between players

### Debugging
- Enable **verbose mode** for detailed network logs
- Check **port availability** with `netstat` commands
- Verify **network connectivity** between devices
- Monitor **UDP traffic** with network analysis tools

## Troubleshooting

### Common Issues

**Problem**: No peers are discovered
- **Solution**: Ensure all devices are on the same subnet
- **Check**: Firewall rules allow UDP port 50999
- **Verify**: Network allows UDP broadcast packets

**Problem**: Messages not being received
- **Solution**: Check if recipient is still active (ping status)
- **Check**: Network connectivity between devices
- **Try**: Restart the application to refresh connections

**Problem**: File transfers fail
- **Solution**: Ensure both users accept the file transfer
- **Check**: Sufficient disk space on receiving device
- **Verify**: No antivirus blocking the transfer

**Problem**: Games desynchronize
- **Solution**: Both players should restart the game
- **Check**: Network stability between players
- **Try**: Use verbose mode to see game message flow

**Problem**: Application crashes on startup
- **Solution**: Check Python version (3.7+ required)
- **Check**: Port 50999 is not already in use
- **Try**: Run with administrator privileges on Windows

### Network Diagnostics
```bash
# Check if port 50999 is open
netstat -ul | grep 50999

# Test UDP connectivity (Linux/macOS)
nc -u [target_ip] 50999

# Check network interface
ip addr show  # Linux
ifconfig      # macOS
ipconfig      # Windows
```

### Log Analysis
Enable verbose mode to see detailed logs including:
- **Message sending/receiving** with full content
- **Peer discovery** and connection events
- **Token validation** and security checks
- **File transfer** progress and errors
- **Game state** changes and moves

## License

This project is created for educational purposes as part of a Computer Networks course. Please check with the course instructors regarding usage and distribution policies.
