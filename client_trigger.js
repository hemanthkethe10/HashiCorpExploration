const { spawn } = require('child_process');
const axios = require('axios');

// --- CONFIGURATION ---
const BOUNDARY_ADDR = 'http://localhost:9200'; 
const AUTH_METHOD_ID = 'ampw_Fmzcsbm9fq';      
const TARGET_ID = 'ttcp_VHhmkcuZYc';          
const LOGIN_NAME = 'admin';
const PASSWORD = 'N3j3kSWO0QEmXxW3J1SL';

async function establishBoundarySession() {
    try {
        console.log("--- 1. Authenticating ---");
        const authRes = await axios.post(`${BOUNDARY_ADDR}/v1/auth-methods/${AUTH_METHOD_ID}:authenticate`, {
            type: 'token',
            attributes: { login_name: LOGIN_NAME, password: PASSWORD }
        });
        const sessionToken = authRes.data.attributes?.token;

        console.log("--- 2. Authorizing Target ---");
        const targetRes = await axios.post(`${BOUNDARY_ADDR}/v1/targets/${TARGET_ID}:authorize-session`, {}, {
            headers: { 'Authorization': `Bearer ${sessionToken}` }
        });
        const authzToken = targetRes.data.authorization_token;

        // STEP 2: Spawn the 'boundary connect' process
        const boundaryProcess = spawn('boundary', [
            'connect',
            '-authz-token', authzToken,

            '-listen-port', '0' // 0 = dynamic port
        ]);

        return new Promise((resolve, reject) => {
            boundaryProcess.stdout.on('data', (data) => {
                const output = data.toString();
                
                // STEP 3: Parse the output to find the local address/port
                const portMatch = output.match(/Port:\s+(\d+)/);
                if (portMatch) {
                    const localPort = portMatch[1];
                    console.log(`Proxy is live at 127.0.0.1:${localPort}`);
                    
                    // Now your Chatbot/Client can talk to 127.0.0.1:localPort
                    resolve({ port: localPort, process: boundaryProcess });
                }
            });

            boundaryProcess.stderr.on('data', (data) => {
                console.error(`Boundary Error: ${data}`);
            });
        });

    } catch (error) {
        console.error("Failed to establish session:", error.response?.data || error.message);
    }
}

// ... (Your existing imports and Authentication logic)

async function runTest() {
    const session = await establishBoundarySession(TARGET_ID);
    
    if (session) {
        console.log(`\nPROXY IS READY on port: ${session.port}`);
        console.log("Keep this terminal open to keep the proxy alive.");
        console.log(`Try this command in a NEW terminal: curl -v http://127.0.0.1:${session.port}`);

        // This keeps the script from exiting
        process.stdin.resume(); 

        // Handle cleanup if you CTRL+C
        process.on('SIGINT', () => {
            console.log("\nShutting down proxy...");
            session.process.kill();
            process.exit();
        });
    }
}

runTest();