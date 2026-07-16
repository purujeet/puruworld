/**
 * Orbit Defender: Deluxe UX Edition (Mobile Orientation Hotfix)
 */
const GAME_CONFIG = {
    BULLET_SPEED: 11,            // Snappier, faster shooting response
    METEOR_BASE_SPEED: 0.9,       // Slower base speed for more reactive play
    ROTATION_SPEED: 0.16,         // Faster, more responsive steering
    BASE_FIRE_RATE: 280, 
    SPAWN_INTERVAL: 1400,         // Slightly more relaxed starting spawn interval
    POWERUP_DROP_CHANCE: 0.40
};

const POWERUP_TYPES = {
    DUAL_SHOT: 'DUAL_SHOT', SPREAD_SHOT: 'SPREAD_SHOT', PLASMA_BEAM: 'PLASMA_BEAM',
    SHIELD: 'SHIELD', SLOW_MO: 'SLOW_MO', SINGULARITY: 'SINGULARITY',
    EXPLOSIVE: 'EXPLOSIVE', OVERDRIVE: 'OVERDRIVE', EMP: 'EMP', REPULSOR: 'REPULSOR'
};

// --- NETWORK STATE ---
window.isMultiplayer = false;
window.myRole = 'single'; // 'defender' (host), 'attacker' (client), or 'single'
window.peer = null;
window.conn = null;

function generateRoomCode() {
    let chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    let code = '';
    for (let i = 0; i < 4; i++) {
        code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return code;
}

function getMeteorCost(type) {
    if (type === 'FAST') return 25;
    if (type === 'TANK') return 40;
    if (type === 'EXPLOSIVE') return 50;
    return 15; // STANDARD
}

// --- SCENE 1: MAIN MENU ---
class MainMenuScene extends Phaser.Scene {
    constructor() { super({ key: 'MainMenuScene' }); }
    
    create() {
        const cx = this.scale.width / 2;
        const cy = this.scale.height / 2;
        
        this.add.text(cx, cy - 140, 'ORBIT DEFENDER', { fontSize: 'clamp(28px, 7vw, 54px)', fontWeight: 'bold', fill: '#00ffcc', fontFamily: 'monospace' }).setOrigin(0.5);
        this.add.text(cx, cy - 80, 'DELUXE MULTIPLAYER', { fontSize: 'clamp(12px, 3.5vw, 18px)', fill: '#ffcc00', fontFamily: 'monospace' }).setOrigin(0.5);
        this.add.text(cx, cy - 10, 'Mac: Move mouse cursor to aim.\nMobile: Drag finger or tap to steer!', { fontSize: 'clamp(13px, 3.5vw, 15px)', fill: '#ffffff', align: 'center', lineHeight: 1.5 }).setOrigin(0.5);
        
        // Single Player Button
        const btnSingle = this.add.text(cx, cy + 70, 'SINGLE PLAYER', { fontSize: '18px', fill: '#ffffff', fontWeight: 'bold', backgroundColor: '#111125', padding: { x: 20, y: 10 } }).setOrigin(0.5).setInteractive({ useHandCursor: true });
        btnSingle.on('pointerover', () => btnSingle.setFill('#00ffcc'));
        btnSingle.on('pointerout', () => btnSingle.setFill('#ffffff'));
        btnSingle.on('pointerdown', () => {
            window.isMultiplayer = false;
            window.myRole = 'single';
            this.scene.start('GameScene');
        });

        // Create Multiplayer Room Button
        const btnCreate = this.add.text(cx, cy + 130, 'CREATE GAME ROOM', { fontSize: '18px', fill: '#ff0055', fontWeight: 'bold', backgroundColor: '#111125', padding: { x: 20, y: 10 } }).setOrigin(0.5).setInteractive({ useHandCursor: true });
        btnCreate.on('pointerover', () => btnCreate.setFill('#ff5588'));
        btnCreate.on('pointerout', () => btnCreate.setFill('#ff0055'));
        btnCreate.on('pointerdown', () => this.handleCreateRoom());

        // Join Multiplayer Room Button
        const btnJoin = this.add.text(cx, cy + 190, 'JOIN GAME ROOM', { fontSize: '18px', fill: '#ffcc00', fontWeight: 'bold', backgroundColor: '#111125', padding: { x: 20, y: 10 } }).setOrigin(0.5).setInteractive({ useHandCursor: true });
        btnJoin.on('pointerover', () => btnJoin.setFill('#ffeb3b'));
        btnJoin.on('pointerout', () => btnJoin.setFill('#ffcc00'));
        btnJoin.on('pointerdown', () => this.handleJoinRoom());
    }

    handleCreateRoom() {
        const code = generateRoomCode();
        const overlay = document.getElementById('lobby-overlay');
        const createSec = document.getElementById('lobby-create-section');
        const joinSec = document.getElementById('lobby-join-section');
        const status = document.getElementById('lobby-status');
        const codeDisp = document.getElementById('room-code-display');

        overlay.style.display = 'flex';
        createSec.style.display = 'block';
        joinSec.style.display = 'none';
        codeDisp.innerText = code;
        status.innerText = 'Creating room in network...';

        window.peer = new Peer('orbit-drop-' + code);
        
        window.peer.on('open', () => {
            status.innerText = 'Room open. Share the code!';
        });

        window.peer.on('connection', (conn) => {
            window.conn = conn;
            window.isMultiplayer = true;
            window.myRole = 'defender'; // Host is defender
            status.innerText = 'Player 2 connected! Starting...';
            
            window.conn.on('open', () => {
                setTimeout(() => {
                    window.conn.send({ type: 'start' });
                    overlay.style.display = 'none';
                    this.scene.start('GameScene');
                }, 1000);
            });
        });

        window.peer.on('error', (err) => {
            console.error(err);
            status.innerText = 'Lobby Error: ' + err.type;
        });

        document.getElementById('lobby-back-btn').onclick = () => this.cleanupLobby();
    }

    handleJoinRoom() {
        const overlay = document.getElementById('lobby-overlay');
        const createSec = document.getElementById('lobby-create-section');
        const joinSec = document.getElementById('lobby-join-section');
        const status = document.getElementById('lobby-status');
        const input = document.getElementById('room-code-input');
        const connectBtn = document.getElementById('join-btn');

        overlay.style.display = 'flex';
        createSec.style.display = 'none';
        joinSec.style.display = 'flex';
        status.innerText = '';
        input.value = '';

        connectBtn.onclick = () => {
            const code = input.value.toUpperCase().trim();
            if (code.length !== 4) {
                status.innerText = 'Please enter a 4-letter code!';
                return;
            }
            status.innerText = 'Connecting to room...';

            window.peer = new Peer();
            window.peer.on('open', () => {
                window.conn = window.peer.connect('orbit-drop-' + code);
                window.isMultiplayer = true;
                window.myRole = 'attacker'; // Client is attacker

                window.conn.on('open', () => {
                    status.innerText = 'Connected! Waiting for host to start...';
                });

                window.conn.on('data', (data) => {
                    if (data.type === 'start') {
                        overlay.style.display = 'none';
                        this.scene.start('GameScene');
                    }
                });

                window.conn.on('close', () => {
                    status.innerText = 'Disconnected from host.';
                });

                window.conn.on('error', (err) => {
                    status.innerText = 'Connection error.';
                });
            });

            window.peer.on('error', (err) => {
                status.innerText = 'Connection initialization failed.';
            });
        };

        document.getElementById('lobby-back-btn').onclick = () => this.cleanupLobby();
    }

    cleanupLobby() {
        if (window.conn) window.conn.close();
        if (window.peer) window.peer.destroy();
        window.isMultiplayer = false;
        window.myRole = 'single';
        document.getElementById('lobby-overlay').style.display = 'none';
    }
}

// --- SCENE 2: CORE GAMEPLAY ---
class GameScene extends Phaser.Scene {
    constructor() { super({ key: 'GameScene' }); }

    init() {
        this.score = 0; this.level = 1; this.nextSpawnTime = 0; this.lastFiredTime = 0;
        this.isGameOver = false; this.isPaused = false; this.speedMultiplier = 1.0; this.activePowerUp = null;
        this.powerUpTimer = 0; this.fireRateModifier = 1.0; this.hasOrbitalShield = false;
        this.shieldHitPoints = 0; this.isSlowMoActive = false; this.isExplosiveActive = false;
        
        this.waveIntermissionActive = false;
        this.meteorsDestroyedThisWave = 0;
        this.meteorsNeededForNextWave = 10;

        this.planetRadius = Math.min(this.scale.width, this.scale.height) * 0.08;
        this.atmosphereRadius = Math.min(this.scale.width, this.scale.height) * 0.45;
        this.targetAngle = 0;

        // Multiplayer initialization
        this.nextSyncTime = 0;
        this.attackerEnergy = 0;
        this.selectedMeteorType = 'STANDARD';
    }

    create() {
        const cx = this.scale.width / 2;
        const cy = this.scale.height / 2;

        this.atmosphereShield = this.add.graphics().lineStyle(2, 0x00ffcc, 0.15).strokeCircle(cx, cy, this.atmosphereRadius);
        
        this.planet = this.add.container(cx, cy);
        let planetBody = this.add.graphics().fillStyle(0x1a2636, 1).lineStyle(3, 0x00ffcc, 1).fillCircle(0, 0, this.planetRadius).strokeCircle(0, 0, this.planetRadius);
        this.planet.add(planetBody);

        this.turret = this.add.graphics().fillStyle(0xff0055, 1).fillRect(-5, -this.planetRadius - 14, 10, 18);
        this.planet.add(this.turret);

        this.shieldGraphics = this.add.graphics();
        this.uiGraphics = this.add.graphics(); // Initialize dynamic UI graphics
        this.bulletsGroup = this.add.group();
        this.meteorsGroup = this.add.group();
        this.powerUpsGroup = this.add.group();

        this.pauseButton = this.add.text(40, 35, '⏸', { fontSize: '24px', fill: '#00ffcc', fontFamily: 'monospace', backgroundColor: '#111125', padding: { x: 10, y: 5 } })
            .setOrigin(0.5)
            .setInteractive({ useHandCursor: true });
            
        this.pauseButton.on('pointerover', () => this.pauseButton.setFill('#ff0055'));
        this.pauseButton.on('pointerout', () => this.pauseButton.setFill('#00ffcc'));
        this.pauseButton.on('pointerdown', (pointer, localX, localY, event) => {
            event.stopPropagation();
            this.togglePause();
        });

        this.scoreText = this.add.text(80, 20, `SCORE: ${this.score}`, { fontSize: '20px', fill: '#ffffff', fontFamily: 'monospace', fontWeight: 'bold' });
        this.waveText = this.add.text(this.scale.width - 145, 20, `WAVE: ${this.level}`, { fontSize: '20px', fill: '#ffcc00', fontFamily: 'monospace', fontWeight: 'bold' });
        this.powerUpStatusText = this.add.text(80, 48, 'SYSTEM: NOMINAL', { fontSize: '13px', fill: '#00ffcc', fontFamily: 'monospace' });

        if (window.isMultiplayer && window.myRole === 'attacker') {
            // Draw control buttons for spawning meteors (Client Attacker only)
            let bx = this.scale.width / 2;
            let by = this.scale.height - 40;
            this.btnStd = this.add.text(bx - 180, by, 'STD [15]', { fontSize: '14px', fill: '#00ffcc', backgroundColor: '#111125', padding: { x: 8, y: 5 } }).setOrigin(0.5).setInteractive({ useHandCursor: true });
            this.btnFast = this.add.text(bx - 60, by, 'FAST [25]', { fontSize: '14px', fill: '#ffffff', backgroundColor: '#111125', padding: { x: 8, y: 5 } }).setOrigin(0.5).setInteractive({ useHandCursor: true });
            this.btnTank = this.add.text(bx + 60, by, 'TANK [40]', { fontSize: '14px', fill: '#ffffff', backgroundColor: '#111125', padding: { x: 8, y: 5 } }).setOrigin(0.5).setInteractive({ useHandCursor: true });
            this.btnExpl = this.add.text(bx + 180, by, 'EXPL [50]', { fontSize: '14px', fill: '#ffffff', backgroundColor: '#111125', padding: { x: 8, y: 5 } }).setOrigin(0.5).setInteractive({ useHandCursor: true });
            this.energyText = this.add.text(25, this.scale.height - 40, 'ENERGY: 0', { fontSize: '16px', fill: '#ffcc00', fontFamily: 'monospace', fontWeight: 'bold' });

            this.btnStd.on('pointerdown', (p, lx, ly, e) => { e.stopPropagation(); this.selectedMeteorType = 'STANDARD'; });
            this.btnFast.on('pointerdown', (p, lx, ly, e) => { e.stopPropagation(); this.selectedMeteorType = 'FAST'; });
            this.btnTank.on('pointerdown', (p, lx, ly, e) => { e.stopPropagation(); this.selectedMeteorType = 'TANK'; });
            this.btnExpl.on('pointerdown', (p, lx, ly, e) => { e.stopPropagation(); this.selectedMeteorType = 'EXPLOSIVE'; });

            // Pointer input to send spawn trigger
            this.input.on('pointerdown', (pointer) => {
                if (pointer.y > this.scale.height - 80 || this.isPaused) return;
                
                let cost = getMeteorCost(this.selectedMeteorType);
                if (this.attackerEnergy >= cost) {
                    this.attackerEnergy -= cost;
                    let angle = Phaser.Math.Angle.Between(this.scale.width / 2, this.scale.height / 2, pointer.x, pointer.y);
                    window.conn.send({ type: 'spawn', meteorType: this.selectedMeteorType, angle: angle });
                }
            });
        }

        // Host listener for inbound spawns
        if (window.isMultiplayer && window.myRole === 'defender') {
            window.conn.on('data', (data) => {
                if (data.type === 'spawn') {
                    this.spawnMultiplayerMeteor(data.meteorType, data.angle);
                }
            });
        }



        // Client listener for host sync states
        if (window.isMultiplayer && window.myRole === 'attacker') {
            window.conn.on('data', (data) => {
                if (data.type === 'sync') {
                    const cx = this.scale.width / 2;
                    const cy = this.scale.height / 2;
                    
                    this.score = data.score;
                    this.level = data.level;
                    this.planet.rotation = data.planetRotation;
                    this.hasOrbitalShield = data.hasShield;
                    this.shieldHitPoints = data.shieldHp;
                    this.activePowerUp = data.powerUp;
                    this.powerUpTimer = data.powerUpTimer;
                    this.meteorsDestroyedThisWave = data.meteorsDestroyed;
                    this.meteorsNeededForNextWave = data.meteorsNeeded;

                    // Sync graphics objects
                    this.bulletsGroup.clear(true, true);
                    this.meteorsGroup.clear(true, true);
                    this.powerUpsGroup.clear(true, true);

                    data.bullets.forEach(b => {
                        let laser = this.add.graphics().fillStyle(b.isPiercing ? 0xcc00ff : 0x00ffcc, 1).fillRect(-2, -8, 4, 16);
                        laser.x = cx + b.x; laser.y = cy + b.y; laser.rotation = b.rotation;
                        this.bulletsGroup.add(laser);
                    });

                    data.meteors.forEach(m => {
                        let meteor = this.add.graphics();
                        let color = 0x594a4a;
                        let strokeColor = 0xff5533;
                        if (m.type === 'FAST') { color = 0x00ffff; strokeColor = 0xffffff; }
                        else if (m.type === 'TANK') { color = 0x734a12; strokeColor = 0xff0000; }
                        else if (m.type === 'EXPLOSIVE') { color = 0xff3300; strokeColor = 0xffff00; }

                        meteor.fillStyle(color, 1).lineStyle(2, strokeColor, 1).strokeCircle(0, 0, m.radius).fillCircle(0, 0, m.radius);
                        meteor.x = cx + m.x; meteor.y = cy + m.y;
                        this.meteorsGroup.add(meteor);
                    });

                    data.powerups.forEach(item => {
                        let p = this.add.graphics().fillStyle(0x33ff00, 1).lineStyle(2, 0xffffff, 1).fillCircle(0, 0, 9).strokeCircle(0, 0, 9);
                        p.x = cx + item.x; p.y = cy + item.y;
                        this.powerUpsGroup.add(p);
                    });
                }
            });
        }
    }

    update(time, delta) {
        if (this.isGameOver || this.isPaused) return;

        if (window.isMultiplayer && window.myRole === 'attacker') {
            // Client side logic
            this.attackerEnergy = Math.min(100, this.attackerEnergy + delta * 0.01); // Regenerates 10 energy per second
            this.energyText.setText(`ENERGY: ${Math.floor(this.attackerEnergy)}`);

            // Highlight selected button
            this.btnStd.setFill(this.selectedMeteorType === 'STANDARD' ? '#00ffcc' : '#ffffff');
            this.btnFast.setFill(this.selectedMeteorType === 'FAST' ? '#00ffcc' : '#ffffff');
            this.btnTank.setFill(this.selectedMeteorType === 'TANK' ? '#00ffcc' : '#ffffff');
            this.btnExpl.setFill(this.selectedMeteorType === 'EXPLOSIVE' ? '#00ffcc' : '#ffffff');
            
            this.drawUI(time);
            return;
        }

        this.handleMotionTracking();
        this.handleAutomaticShooting(time);
        this.handleMeteorSpawning(time);
        this.physicsSystemUpdate(time);
        this.drawShieldLayer();
        this.drawUI(time);

        // Host state broadcast
        if (window.isMultiplayer && window.myRole === 'defender' && time > this.nextSyncTime) {
            this.nextSyncTime = time + 50;
            this.sendStateSync();
        }
    }

    sendStateSync() {
        if (!window.conn) return;
        const cx = this.scale.width / 2;
        const cy = this.scale.height / 2;
        window.conn.send({
            type: 'sync',
            score: this.score,
            level: this.level,
            planetRotation: this.planet.rotation,
            hasShield: this.hasOrbitalShield,
            shieldHp: this.shieldHitPoints,
            powerUp: this.activePowerUp,
            powerUpTimer: this.powerUpTimer,
            meteorsDestroyed: this.meteorsDestroyedThisWave,
            meteorsNeeded: this.meteorsNeededForNextWave,
            bullets: this.bulletsGroup.getChildren().map(b => ({
                x: b.x - cx, y: b.y - cy, rotation: b.rotation, isPiercing: b.isPiercing
            })),
            meteors: this.meteorsGroup.getChildren().map(m => ({
                x: m.x - cx, y: m.y - cy, radius: m.hitRadius, type: m.meteorType
            })),
            powerups: this.powerUpsGroup.getChildren().map(p => ({
                x: p.x - cx, y: p.y - cy, type: p.powerUpType
            }))
        });
    }

    handleMotionTracking() {
        if (this.isPaused || (window.isMultiplayer && window.myRole === 'attacker')) return;
        const cx = this.scale.width / 2;
        const cy = this.scale.height / 2;
        const pointer = this.input.activePointer;

        if (pointer.isDown || pointer.x !== 0 || pointer.y !== 0) {
            let radians = Phaser.Math.Angle.Between(cx, cy, pointer.x, pointer.y);
            this.targetAngle = radians + Math.PI / 2;
            this.planet.rotation = Phaser.Math.Angle.RotateTo(this.planet.rotation, this.targetAngle, GAME_CONFIG.ROTATION_SPEED);
        }
    }

    handleAutomaticShooting(time) {
        if (this.waveIntermissionActive) return;

        if (time > this.lastFiredTime) {
            this.fireActiveWeaponSystem();
            this.lastFiredTime = time + (GAME_CONFIG.BASE_FIRE_RATE * this.fireRateModifier);
        }
    }

    fireActiveWeaponSystem() {
        const cx = this.scale.width / 2;
        const cy = this.scale.height / 2;
        const baseAngle = this.planet.rotation - Math.PI / 2;

        if (this.activePowerUp === POWERUP_TYPES.SPREAD_SHOT) {
            this.instantiateLaser(cx, cy, baseAngle - 0.2);
            this.instantiateLaser(cx, cy, baseAngle);
            this.instantiateLaser(cx, cy, baseAngle + 0.2);
        } else if (this.activePowerUp === POWERUP_TYPES.DUAL_SHOT) {
            this.instantiateLaser(cx, cy, baseAngle, -8);
            this.instantiateLaser(cx, cy, baseAngle, 8);
        } else if (this.activePowerUp === POWERUP_TYPES.PLASMA_BEAM) {
            this.instantiateLaser(cx, cy, baseAngle, 0, 2.5, true);
        } else {
            this.instantiateLaser(cx, cy, baseAngle);
        }

        this.tweens.add({ targets: this.turret, y: 5, duration: 40, yoyo: true });
    }

    instantiateLaser(cx, cy, angle, parallelOffset = 0, scaleMultiplier = 1.0, isPiercing = false) {
        let laser = this.add.graphics().fillStyle(isPiercing ? 0xcc00ff : 0x00ffcc, 1).fillRect(-2 * scaleMultiplier, -8, 4 * scaleMultiplier, 16);
        const radius = this.planetRadius + 14;

        laser.x = cx + Math.cos(angle) * radius + Math.cos(angle + Math.PI/2) * parallelOffset;
        laser.y = cy + Math.sin(angle) * radius + Math.sin(angle + Math.PI/2) * parallelOffset;
        laser.rotation = angle + Math.PI / 2;
        laser.velocityNSX = Math.cos(angle) * GAME_CONFIG.BULLET_SPEED;
        laser.velocityNSY = Math.sin(angle) * GAME_CONFIG.BULLET_SPEED;
        laser.isPiercing = isPiercing;

        this.bulletsGroup.add(laser);
    }

    handleMeteorSpawning(time) {
        if (window.isMultiplayer || this.waveIntermissionActive || time < this.nextSpawnTime) return;

        this.spawnMeteoroid();
        const interval = GAME_CONFIG.SPAWN_INTERVAL - (this.level * 40); // More gradual decrease in spawn interval
        this.nextSpawnTime = time + Math.max(500, interval);            // Hard minimum limit of 500ms between spawns
    }

    spawnMeteoroid() {
        this.spawnMultiplayerMeteor('STANDARD', Phaser.Math.FloatBetween(0, Math.PI * 2));
    }

    spawnMultiplayerMeteor(type, angle) {
        const cx = this.scale.width / 2;
        const cy = this.scale.height / 2;
        
        let meteor = this.add.graphics();
        
        let size = 24; // Standard size
        let hitPoints = 1;
        let color = 0x594a4a;
        let strokeColor = 0xff5533;
        
        if (type === 'FAST') {
            size = 14;
            color = 0x00ffff; // Cyan
            strokeColor = 0xffffff;
        } else if (type === 'TANK') {
            size = 38;
            hitPoints = 3;
            color = 0x734a12; // Dark brown
            strokeColor = 0xff0000;
        } else if (type === 'EXPLOSIVE') {
            size = 26;
            color = 0xff3300; // Red-orange
            strokeColor = 0xffff00;
        }
        
        meteor.fillStyle(color, 1).lineStyle(2, strokeColor, 1).strokeCircle(0, 0, size / 2).fillCircle(0, 0, size / 2);
        meteor.distanceFromCenter = this.atmosphereRadius;
        meteor.spawnAngle = angle;
        meteor.hitRadius = size / 2;
        meteor.hitPoints = hitPoints;
        meteor.meteorType = type;

        meteor.x = cx + Math.cos(angle) * meteor.distanceFromCenter;
        meteor.y = cy + Math.sin(angle) * meteor.distanceFromCenter;

        this.meteorsGroup.add(meteor);
    }

    physicsSystemUpdate(time) {
        const cx = this.scale.width / 2;
        const cy = this.scale.height / 2;
        let baseSpeed = GAME_CONFIG.METEOR_BASE_SPEED * this.speedMultiplier;
        if (this.isSlowMoActive) baseSpeed *= 0.5;

        if (this.activePowerUp && time > this.powerUpTimer) this.clearPowerUpState();

        this.bulletsGroup.getChildren().forEach(b => {
            b.x += b.velocityNSX; b.y += b.velocityNSY;
            if (b.x < 0 || b.x > this.scale.width || b.y < 0 || b.y > this.scale.height) {
                this.bulletsGroup.remove(b); b.destroy();
            }
        });

        this.powerUpsGroup.getChildren().forEach(item => {
            item.distanceFromCenter -= 1.5; // Power-ups fall much faster towards the planet (easier to grab)
            item.x = cx + Math.cos(item.angleTrack) * item.distanceFromCenter;
            item.y = cy + Math.sin(item.angleTrack) * item.distanceFromCenter;
            item.setScale(1 + Math.sin(time * 0.01) * 0.15);

            if (item.distanceFromCenter <= this.planetRadius + 12) {
                this.applyPowerUp(item.powerUpType, time);
                this.powerUpsGroup.remove(item); item.destroy();
            }
        });

        this.meteorsGroup.getChildren().forEach(m => {
            let speed = baseSpeed;
            if (m.meteorType === 'FAST') speed *= 1.8;
            else if (m.meteorType === 'TANK') speed *= 0.6;
            else if (m.meteorType === 'EXPLOSIVE') speed *= 0.9;

            m.distanceFromCenter -= speed;
            m.x = cx + Math.cos(m.spawnAngle) * m.distanceFromCenter;
            m.y = cy + Math.sin(m.spawnAngle) * m.distanceFromCenter;

            if (m.distanceFromCenter <= this.planetRadius + m.hitRadius) {
                if (this.hasOrbitalShield) {
                    let damage = m.meteorType === 'EXPLOSIVE' ? 3 : 1;
                    this.shieldHitPoints -= damage;
                    this.triggerHapticFeedback(100);
                    this.createExplosionEffect(m.x, m.y, 0x00ffcc, 8);
                    this.meteorsGroup.remove(m); m.destroy();
                    if (this.shieldHitPoints <= 0) this.hasOrbitalShield = false;
                } else {
                    this.triggerGameOver();
                }
            }
        });

        this.bulletsGroup.getChildren().forEach(b => {
            this.meteorsGroup.getChildren().forEach(m => {
                if (Phaser.Math.Distance.Between(b.x, b.y, m.x, m.y) < m.hitRadius + 5) {
                    if (!b.isPiercing) { this.bulletsGroup.remove(b); b.destroy(); }
                    
                    if (m.hitPoints && m.hitPoints > 1) {
                        m.hitPoints--;
                        this.createExplosionEffect(b.x, b.y, 0xffaa00, 5);
                        this.triggerHapticFeedback(20);
                        m.setScale(0.8 + 0.2 * (m.hitPoints / 3));
                    } else {
                        this.processMeteorDestruction(m);
                    }
                }
            });
        });
    }

    processMeteorDestruction(meteor) {
        this.createExplosionEffect(meteor.x, meteor.y, 0xffaa00, meteor.hitRadius);
        this.triggerHapticFeedback(40);

        if (meteor.meteorType === 'EXPLOSIVE') {
            this.meteorsGroup.getChildren().forEach(target => {
                if (target !== meteor && Phaser.Math.Distance.Between(meteor.x, meteor.y, target.x, target.y) < 100) {
                    this.time.delayedCall(40, () => this.processMeteorDestruction(target));
                }
            });
            this.createExplosionEffect(meteor.x, meteor.y, 0xff3300, 20);
        }

        if (this.isExplosiveActive) {
            this.meteorsGroup.getChildren().forEach(target => {
                if (target !== meteor && Phaser.Math.Distance.Between(meteor.x, meteor.y, target.x, target.y) < 85) {
                    this.time.delayedCall(30, () => this.processMeteorDestruction(target));
                }
            });
        }

        if (Math.random() < GAME_CONFIG.POWERUP_DROP_CHANCE) {
            this.spawnPowerUpCollectible(meteor.x, meteor.y, meteor.spawnAngle, meteor.distanceFromCenter);
        }

        this.meteorsGroup.remove(meteor); meteor.destroy();
        this.score += 10; this.scoreText.setText(`SCORE: ${this.score}`);
        
        this.meteorsDestroyedThisWave++;
        if (this.meteorsDestroyedThisWave >= this.meteorsNeededForNextWave) {
            this.triggerNextWaveIntermission();
        }
    }

    spawnPowerUpCollectible(x, y, angle, distance) {
        let item = this.add.graphics();
        item.fillStyle(0x33ff00, 1).lineStyle(2, 0xffffff, 1);
        item.fillCircle(0, 0, 9).strokeCircle(0, 0, 9);

        item.x = x; item.y = y; item.angleTrack = angle; item.distanceFromCenter = distance;
        item.powerUpType = Phaser.Math.RND.pick(Object.values(POWERUP_TYPES));
        this.powerUpsGroup.add(item);
    }

    applyPowerUp(type, currentTime) {
        this.clearPowerUpState();
        this.activePowerUp = type;
        this.powerUpTimer = currentTime + 7000;
        this.displayFloatingNotification(type);
        this.triggerHapticFeedback(150);

        this.powerUpStatusText.setText(`MODIFIER: ${type.replace('_', ' ')}`).setFill('#ffcc00');

        if (type === POWERUP_TYPES.OVERDRIVE) this.fireRateModifier = 0.40;
        if (type === POWERUP_TYPES.SHIELD) { this.hasOrbitalShield = true; this.shieldHitPoints = 3; }
        if (type === POWERUP_TYPES.SLOW_MO) this.isSlowMoActive = true;
        if (type === POWERUP_TYPES.EXPLOSIVE) this.isExplosiveActive = true;
        if (type === POWERUP_TYPES.EMP) this.executeEmpShockwave();
        if (type === POWERUP_TYPES.REPULSOR) this.executeRepulsorPush();
        if (type === POWERUP_TYPES.SINGULARITY) this.executeSingularityStrike();
    }

    clearPowerUpState() {
        this.activePowerUp = null; this.fireRateModifier = 1.0;
        this.isSlowMoActive = false; this.isExplosiveActive = false;
        this.powerUpStatusText.setText('SYSTEM: NOMINAL').setFill('#00ffcc');
    }

    togglePause() {
        if (this.isGameOver) return;
        this.isPaused = !this.isPaused;
        if (this.isPaused) {
            this.pauseButton.setText('▶');
            this.pauseStartTime = this.time.now;
            
            this.pauseOverlay = this.add.graphics();
            this.pauseOverlay.fillStyle(0x030307, 0.7);
            this.pauseOverlay.fillRect(0, 0, this.scale.width, this.scale.height);
            
            this.pauseText = this.add.text(this.scale.width / 2, this.scale.height / 2, 'GAME PAUSED', { 
                fontSize: '36px', 
                fill: '#00ffcc', 
                fontWeight: 'bold', 
                fontFamily: 'monospace' 
            }).setOrigin(0.5);
            
            this.tweens.pauseAll();
        } else {
            this.pauseButton.setText('⏸');
            
            let pauseDuration = this.time.now - this.pauseStartTime;
            this.nextSpawnTime += pauseDuration;
            this.lastFiredTime += pauseDuration;
            if (this.powerUpTimer > 0) {
                this.powerUpTimer += pauseDuration;
            }
            
            if (this.pauseOverlay) this.pauseOverlay.destroy();
            if (this.pauseText) this.pauseText.destroy();
            
            this.tweens.resumeAll();
        }
    }

    triggerNextWaveIntermission() {
        this.waveIntermissionActive = true;
        this.meteorsDestroyedThisWave = 0;
        this.level++;
        this.speedMultiplier += 0.08; // More gradual speed multiplier ramp-up per wave (was 0.15)
        this.meteorsNeededForNextWave = Math.floor(10 + (this.level * 2));

        this.bulletsGroup.clear(true, true);
        this.meteorsGroup.clear(true, true); // Clear active meteoroids on wave transition

        let banner = this.add.text(this.scale.width / 2, this.scale.height / 2 - 60, `WAVE ${this.level - 1} CLEARED`, { fontSize: '32px', fill: '#00ffcc', fontFamily: 'monospace', fontWeight: 'bold' }).setOrigin(0.5);
        let subBanner = this.add.text(this.scale.width / 2, this.scale.height / 2 - 10, 'PREPARE SYSTEMS', { fontSize: '16px', fill: '#ffffff', fontFamily: 'monospace' }).setOrigin(0.5);

        this.tweens.add({
            targets: [banner, subBanner], alpha: { start: 1, end: 0 }, duration: 600, delay: 2000,
            onComplete: () => {
                banner.destroy(); subBanner.destroy();
                this.waveText.setText(`WAVE: ${this.level}`);
                this.waveIntermissionActive = false;
            }
        });
    }

    executeEmpShockwave() {
        const cx = this.scale.width / 2;
        const cy = this.scale.height / 2;
        
        // Create shockwave graphics object
        let shockwave = this.add.graphics();
        let waveState = { radius: this.planetRadius };
        
        this.tweens.add({
            targets: waveState,
            radius: this.planetRadius + 220, // Expands past the atmosphere
            duration: 900,                    // Expanding in a visual, slow-motion pace
            ease: 'Quad.easeOut',
            onUpdate: () => {
                shockwave.clear();
                // Fade line and fill opacity as it expands
                let progress = (waveState.radius - this.planetRadius) / 220;
                let alpha = 1 - progress;
                
                shockwave.lineStyle(5, 0x00ffff, alpha * 0.9);
                shockwave.fillStyle(0x00ffff, alpha * 0.15);
                shockwave.fillCircle(cx, cy, waveState.radius);
                shockwave.strokeCircle(cx, cy, waveState.radius);
                
                // Destroy meteors as the wave reaches them
                let activeMeteors = [...this.meteorsGroup.getChildren()];
                activeMeteors.forEach(m => {
                    if (m.active && m.distanceFromCenter <= waveState.radius) {
                        this.processMeteorDestruction(m);
                    }
                });
            },
            onComplete: () => {
                shockwave.destroy();
            }
        });
        
        // Subtle screen flash to accompany the explosion
        this.cameras.main.flash(150, 0, 255, 255, false);
    }

    executeRepulsorPush() {
        this.meteorsGroup.getChildren().forEach(m => {
            this.tweens.add({ targets: m, distanceFromCenter: Math.min(this.atmosphereRadius - 15, m.distanceFromCenter + 140), duration: 250 });
        });
    }

    executeSingularityStrike() {
        const cx = this.scale.width / 2; const cy = this.scale.height / 2;
        let h = this.add.graphics().fillStyle(0x000000, 1).lineStyle(3, 0xcc00ff, 1).fillCircle(cx, cy - 130, 35).strokeCircle(cx, cy - 130, 35);
        h.alpha = 0;
        this.tweens.add({
            targets: h, alpha: 0.9, duration: 200, yoyo: true, hold: 2200,
            onStart: () => {
                this.meteorsGroup.getChildren().forEach(m => {
                    if (Phaser.Math.Distance.Between(m.x, m.y, cx, cy - 130) < 220) {
                        this.tweens.add({ targets: m, x: cx, y: cy - 130, distanceFromCenter: 130, duration: 450, onComplete: () => this.processMeteorDestruction(m) });
                    }
                });
            },
            onComplete: () => h.destroy()
        });
    }

    drawShieldLayer() {
        this.shieldGraphics.clear();
        if (this.hasOrbitalShield) {
            this.shieldGraphics.lineStyle(4, 0x00ffcc, 0.55);
            this.shieldGraphics.strokeCircle(this.scale.width / 2, this.scale.height / 2, this.planetRadius + 9);
        }
    }

    drawUI(time) {
        this.uiGraphics.clear();
        
        // 1. Draw Wave Progress Bar (Right Side)
        const rx = this.scale.width - 145;
        const ry = 48;
        const rWidth = 120;
        const rHeight = 6;
        
        let waveProgress = Phaser.Math.Clamp(this.meteorsDestroyedThisWave / this.meteorsNeededForNextWave, 0, 1);
        
        // Track background
        this.uiGraphics.fillStyle(0x111125, 1);
        this.uiGraphics.fillRect(rx, ry, rWidth, rHeight);
        this.uiGraphics.lineStyle(1, 0x555577, 0.5);
        this.uiGraphics.strokeRect(rx, ry, rWidth, rHeight);
        
        // Fill track (yellow/orange for wave progress)
        if (waveProgress > 0) {
            this.uiGraphics.fillStyle(0xffcc00, 0.8);
            this.uiGraphics.fillRect(rx + 1, ry + 1, (rWidth - 2) * waveProgress, rHeight - 2);
        }
        
        // 2. Draw Power-up Duration Progress Bar (Left Side)
        if (this.activePowerUp) {
            const lx = 80;
            const ly = 73;
            const lWidth = 150;
            const lHeight = 6;
            
            let remaining = this.powerUpTimer - time;
            let powerProgress = Phaser.Math.Clamp(remaining / 7000, 0, 1);
            
            // Track background
            this.uiGraphics.fillStyle(0x111125, 1);
            this.uiGraphics.fillRect(lx, ly, lWidth, lHeight);
            this.uiGraphics.lineStyle(1, 0x555577, 0.5);
            this.uiGraphics.strokeRect(lx, ly, lWidth, lHeight);
            
            // Fill track (cyan for active power)
            if (powerProgress > 0) {
                this.uiGraphics.fillStyle(0x00ffcc, 0.8);
                this.uiGraphics.fillRect(lx + 1, ly + 1, (lWidth - 2) * powerProgress, lHeight - 2);
            }
        }
    }

    displayFloatingNotification(text) {
        let txt = this.add.text(this.scale.width/2, this.scale.height/2 - 90, text.replace('_',' '), { fontSize: '18px', fill: '#ffcc00', fontWeight: 'bold', fontFamily: 'monospace' }).setOrigin(0.5);
        this.tweens.add({ targets: txt, y: txt.y - 35, alpha: 0, duration: 1100, onComplete: () => txt.destroy() });
    }

    createExplosionEffect(x, y, color, intensity) {
        const particleCount = Math.min(15, Math.floor(intensity / 2) + 5);
        for (let i = 0; i < particleCount; i++) {
            let p = this.add.graphics().fillStyle(color, 1).fillCircle(0, 0, 2.5);
            p.x = x; p.y = y;
            let a = Phaser.Math.FloatBetween(0, Math.PI * 2);
            let s = Phaser.Math.FloatBetween(1.2, 4);
            this.tweens.add({ targets: p, x: x + Math.cos(a) * (s * 14), y: y + Math.sin(a) * (s * 14), alpha: 0, duration: 300, onComplete: () => p.destroy() });
        }
        if (intensity > 25) this.cameras.main.shake(120, 0.015);
    }

    triggerHapticFeedback(duration) {
        if (window.navigator && window.navigator.vibrate) {
            window.navigator.vibrate(duration);
        }
    }

    triggerGameOver() {
        this.isGameOver = true; 
        if (this.pauseButton) this.pauseButton.destroy();
        this.triggerHapticFeedback([300, 100, 300]); 
        this.cameras.main.shake(500, 0.04);

        if (window.isMultiplayer && window.conn) {
            window.conn.send({
                type: 'sync',
                score: this.score,
                level: this.level,
                planetRotation: this.planet.rotation,
                hasShield: false,
                shieldHp: 0,
                powerUp: null,
                powerUpTimer: 0,
                meteorsDestroyed: this.meteorsDestroyedThisWave,
                meteorsNeeded: this.meteorsNeededForNextWave,
                bullets: [],
                meteors: [],
                powerups: []
            });
        }

        this.time.delayedCall(600, () => this.scene.start('GameOverScene', { score: this.score }));
    }
}

// --- SCENE 3: GAME OVER ---
class GameOverScene extends Phaser.Scene {
    constructor() { super({ key: 'GameOverScene' }); }
    
    create(data) {
        const cx = this.scale.width / 2; const cy = this.scale.height / 2;
        this.add.text(cx, cy - 60, 'CORE BREACHED', { fontSize: '36px', fill: '#ff0055', fontWeight: 'bold', fontFamily: 'monospace' }).setOrigin(0.5);
        this.add.text(cx, cy + 10, `FINAL SCORE: ${data.score || 0}`, { fontSize: '20px', fill: '#ffffff', fontFamily: 'monospace' }).setOrigin(0.5);
        
        if (!window.isMultiplayer || window.myRole === 'defender') {
            const btn = this.add.text(cx, cy + 90, 'REDEPLOY PLANET', { fontSize: '18px', fill: '#00ffcc', backgroundColor: '#111125', padding: { x: 20, y: 10 } }).setOrigin(0.5).setInteractive({ useHandCursor: true });
            btn.on('pointerdown', () => {
                if (window.isMultiplayer && window.conn) {
                    window.conn.send({ type: 'start' });
                }
                this.scene.start('GameScene');
            });
        } else {
            const status = this.add.text(cx, cy + 90, 'WAITING FOR HOST TO REDEPLOY', { fontSize: '16px', fill: '#8888aa', fontFamily: 'monospace' }).setOrigin(0.5);
            
            if (window.conn) {
                window.conn.on('data', (data) => {
                    if (data.type === 'start') {
                        this.scene.start('GameScene');
                    }
                });
            }
        }
    }
}

const config = {
    type: Phaser.AUTO,
    width: window.innerWidth,
    height: window.innerHeight,
    scale: { mode: Phaser.Scale.RESIZE, autoCenter: Phaser.Scale.CENTER_BOTH },
    backgroundColor: '#030307',
    parent: 'game-container',
    scene: [MainMenuScene, GameScene, GameOverScene],
    fps: { target: 60, forceSetTimeOut: true }
};
const game = new Phaser.Game(config);

