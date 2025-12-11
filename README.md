### Tech Stack

- **Language:** Python 3.10+
    
- **Networking:** Raw TCP/UDP Sockets, HTTP Protocol.
    
- **Concurrency:** asyncio (Coroutines) + threading.
    
- **Binary Processing:** struct packing/unpacking, Bitwise operations.
    
- **GUI:** customtkinter (Modern Tkinter wrapper) with PIL (Image processing).
    
- **System:** psutil for hardware diagnostic

- 
Here is the detailed breakdown of the **8 Major Problems** I faced, the **Process** we used to solve them, and the **Architecture** behind FluxTorrent.

---

### 1. The "Alien Language" Problem (Bencoding)

**The Problem:**  
Torrent files (.torrent) are not readable text files like JSON or XML. They use a unique binary format called **Bencoding**. Standard Python libraries cannot read them. If you try to open one in a text editor, it looks like gibberish (d4:infod6:lengthi...).

**The Process & Solution:**

- We wrote a **Recursive Descent Parser** from scratch.
    
- We created a Decoder class that scans the file byte-by-byte.
    
- It looks for markers: i for integers, s for strings, l for lists, and d for dictionaries.
    
- **The Critical Step:** We had to calculate the **Info Hash**. This required taking the raw binary info dictionary and running a SHA-1 hash on it. This hash is the "Passport" we use to prove to other computers that we are looking for the same file.
    

### 2. The "Where is Everybody?" Problem (Tracker Protocols)

**The Problem:**  
We had the file metadata, but we didn't know IP addresses of people who had the data. We needed to ask a **Tracker Server**.

**The Process & Solution:**

- We implemented two distinct networking protocols: **HTTP** and **UDP**.
    
- **UDP was the Hardest:** UDP is "connectionless," meaning you send data and pray it arrives.
    
- We had to manually pack binary C-structs (struct.pack('>QII'...)) to create the request. We had to fake a "Transaction ID" to ensure the response we got belonged to us.
    
- **Parsing Peers:** The tracker returns a "Compact Peer List"—a long string of bytes where every 6 bytes represents a person (4 bytes for IP, 2 bytes for Port). We had to slice and decode this to build our candidate list.
    

### 3. The "Silent Treatment" Problem (Handshakes)

**The Problem:**  
Even after finding IP addresses, when we tried to connect, they would immediately disconnect.

**The Process & Solution:**

- BitTorrent peers are paranoid. If you don't speak the exact protocol, they ban you.
    
- We implemented the **BitTorrent Handshake**:
    
    - 1 byte: Protocol String Length (19)
        
    - 19 bytes: "BitTorrent protocol"
        
    - 8 bytes: Reserved bits (set to 0)
        
    - 20 bytes: **Info Hash** (The ID of the file)
        
    - 20 bytes: **Peer ID** (Our generated ID: -FX0001-...)
        
- If we sent even one byte wrong, the handshake failed. We used asyncio to perform this handshake on 100+ peers simultaneously.
    

### 4. The "Piece 0" Infinite Loop (Logic Bug)

**The Problem:**  
At one point, the client was downloading "Piece 0" over and over again. It would finish it, verify it, and then download it again.

**The Process & Solution:**

- This was a **State Management** failure in the PieceManager.
    
- We split the pieces into three lists: missing, ongoing, and have.
    
- The bug was that we weren't removing the piece from the missing list after it finished.
    
- **The Fix:** We implemented strict state transitions. When a piece is verified, it is aggressively removed from missing and ongoing. We also added a **Bitfield** (a binary map) to track exactly what we have to prevent re-downloading.
    

### 5. The "Linear Slowdown" Problem

**The Problem:**  
The client was downloading Piece 0, then Piece 1, then Piece 2.  
This is terrible for speed because if "Piece 5" is rare, the download stops entirely waiting for it.

**The Process & Solution:**

- **Randomization:** We shuffled the missing_pieces list using random.shuffle().
    
- **Availability Check:** Before asking a peer for a random piece, we check their **Bitfield** (the map of pieces they have).
    
- We only request a piece if:
    
    1. We need it.
        
    2. They have it.
        
    3. No one else is currently downloading it.
        

### 6. The Speed Limit (1MB/s Cap)

**The Problem:**  
Downloading was working, but it was slow (~900KB/s). This was because we were doing "Stop-and-Wait" (Request -> Wait for Data -> Request Next).

**The Process & Solution:**

- **Aggressive Pipelining:** We removed the "Wait". We started sending 10 to 20 requests at the same time into the TCP stream.
    
- **Socket Tuning:** We increased the Python socket buffer size from the default 64KB to **256KB** (limit=2**18). This reduced CPU context switching.
    
- **Swarm Churning:** We built a background loop that kills slow peers every 10 seconds and replaces them with fresh ones. This ensures we are always connected to the fastest available uploaders.
    

### 7. The "Endgame" Stall (99% Stuck)

**The Problem:**  
The download would hit 99% and stop forever. This happens because the last few pieces were assigned to peers that suddenly disconnected or became extremely slow.

**The Process & Solution:**

- We implemented **Endgame Mode**.
    
- Usually, we forbid two peers from downloading the same piece (to save bandwidth).
    
- **The Fix:** When missing_pieces < 5, we throw the rulebook out. We allow **Double Downloading**. We ask every connected peer for the final pieces. Whoever sends the data first wins; the others are discarded. This ensures the file actually finishes.
    

### 8. The "Freezing UI" (Architecture)

**The Problem:**  
When the download started, the window would freeze and become unresponsive. This is because the Download Loop was blocking the GUI Loop.

**The Process & Solution:**

- **Threading & Asyncio Hybrid:**
    
    - The **GUI** runs on the Main Thread (Required by Windows/MacOS).
        
    - The **Torrent Engine** runs on a background Daemon Thread.
        
    - Inside the background thread, we run an **Asyncio Event Loop**.
        
- This separation allows the UI to redraw animations (Cyberpunk Neon effects) at 60FPS while the engine crunches gigabytes of data in the background.
    

---

