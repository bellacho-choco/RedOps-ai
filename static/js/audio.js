/**
 * REDOPS-AI - Web Audio API Sound Synthesizer
 * Generates telemetry audio and terminal beeps without external files
 */

class NeuralAudioSynth {
    constructor() {
        this.ctx = null;
        this.enabled = true;
    }

    init() {
        if (!this.ctx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
        }
    }

    playBeep(freq = 880, type = 'sine', duration = 0.05, gainVal = 0.08) {
        if (!this.enabled) return;
        this.init();
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }

        try {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.type = type;
            osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(freq * 0.5, this.ctx.currentTime + duration);

            gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

            osc.connect(gain);
            gain.connect(this.ctx.destination);

            osc.start();
            osc.stop(this.ctx.currentTime + duration);
        } catch (e) {
            // Audio context policy
        }
    }

    playPacketChime() {
        this.playBeep(1200, 'triangle', 0.04, 0.05);
    }

    playAlertTone() {
        this.playBeep(440, 'sawtooth', 0.15, 0.1);
    }

    playCompromiseStinger() {
        if (!this.enabled) return;
        this.init();
        this.playBeep(980, 'sine', 0.08, 0.1);
        setTimeout(() => this.playBeep(1400, 'sine', 0.12, 0.12), 60);
    }
}

const audioSynth = new NeuralAudioSynth();
