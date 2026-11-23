"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MediaPresence, MediaRecording, MediaSignal } from "./media-client";
import { getMedia, postMedia, recordingMayContinue } from "./media-client";
import styles from "./preferans-media.module.css";

// Public STUN may become unavailable; no TURN relay or paid dependency.
const ICE_SERVERS: RTCIceServer[] = [{ urls: ["stun:stun.l.google.com:19302"] }];
const SEATS = [0, 1, 2];
const label = (seat: number) => `Игрок ${seat + 1}`;
const recordMimes = ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];

type SharedScene = { phase: string; status: string; publicTrick: string[] };

type RecordingResources = {
  recorder: MediaRecorder; stream: MediaStream; context: AudioContext | null;
  interval: ReturnType<typeof setInterval>; chunks: Blob[];
};

function VideoTile({ stream, seat, muted = false }: {
  stream: MediaStream | null; seat: number; muted?: boolean;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => { if (ref.current) ref.current.srcObject = stream; }, [stream]);
  return <div className={styles.videoTile}>
    <span>{label(seat)}</span>
    {stream ? <video ref={ref} autoPlay playsInline muted={muted} data-preferans-media-video /> : <p>Без видео</p>}
  </div>;
}

export function PreferansMedia({ roomId, seat, scene }: {
  roomId: string; seat: number; scene: SharedScene;
}) {
  const [enabled, setEnabled] = useState<MediaPresence>({ audio: false, video: false });
  const [peers, setPeers] = useState<Record<number, MediaPresence>>({});
  const [streams, setStreams] = useState<Record<number, MediaStream>>({});
  const [recording, setRecording] = useState<MediaRecording | null>(null);
  const [error, setError] = useState("");
  const local = useRef<MediaStream | null>(null);
  const connections = useRef<Map<number, RTCPeerConnection>>(new Map());
  const pendingIce = useRef<Map<number, RTCIceCandidateInit[]>>(new Map());
  const channels = useRef<Map<number, RTCDataChannel>>(new Map());
  const cursor = useRef(0);
  const mediaActive = useRef(false);
  const currentRecording = useRef<MediaRecording | null>(null);
  const confirmedAtMs = useRef(0);
  const recordingResources = useRef<RecordingResources | null>(null);
  const sharedScene = useRef(scene);
  const remoteStreams = useRef<Record<number, MediaStream>>({});
  const [localVersion, setLocalVersion] = useState(0);

  useEffect(() => { sharedScene.current = scene; }, [scene]);

  const send = useCallback(async (action: Parameters<typeof postMedia>[1], args: Record<string, unknown> = {}) => {
    await postMedia(roomId, action, args);
  }, [roomId]);

  const signal = useCallback((to: number, kind: MediaSignal["kind"], data: Record<string, unknown>) => {
    void send("signal", { to, kind, data }).catch(() => setError("Не удалось доставить сигнал WebRTC."));
  }, [send]);

  const disposeConnections = useCallback(() => {
    connections.current.forEach(pc => pc.close());
    connections.current.clear();
    channels.current.clear();
    pendingIce.current.clear();
    remoteStreams.current = {};
    setStreams({});
  }, []);

  const offer = useCallback(async (peer: number, pc: RTCPeerConnection) => {
    if (pc.signalingState !== "stable") return;
    try {
      await pc.setLocalDescription(await pc.createOffer());
      if (pc.localDescription) signal(peer, "offer", { type: "offer", sdp: pc.localDescription.sdp ?? "" });
    } catch { setError("Не удалось согласовать WebRTC-соединение."); }
  }, [signal]);

  const ensurePeer = useCallback((peer: number) => {
    if (peer === seat) return null;
    const existing = connections.current.get(peer);
    if (existing && existing.signalingState !== "closed") return existing;
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    connections.current.set(peer, pc);
    pc.onicecandidate = event => {
      if (event.candidate) signal(peer, "ice", event.candidate.toJSON() as unknown as Record<string, unknown>);
    };
    pc.ontrack = event => {
      const stream = event.streams[0] ?? new MediaStream([event.track]);
      remoteStreams.current = { ...remoteStreams.current, [peer]: stream };
      setStreams(remoteStreams.current);
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed") {
        setError("P2P-соединение не установлено. Возможна блокировка NAT; игра продолжает работать.");
      }
    };
    pc.ondatachannel = event => {
      if (event.channel.label === "recording-consent") {
        channels.current.set(peer, event.channel);
        event.channel.onmessage = message => {
          if (message.data === "STOP") {
            const resources = recordingResources.current;
            if (resources && resources.recorder.state !== "inactive") resources.recorder.stop();
          }
        };
      }
    };
    if (seat < peer) {
      const channel = pc.createDataChannel("recording-consent");
      channels.current.set(peer, channel);
      channel.onmessage = message => {
        if (message.data === "STOP") {
          const resources = recordingResources.current;
          if (resources && resources.recorder.state !== "inactive") resources.recorder.stop();
        }
      };
    }
    local.current?.getTracks().forEach(track => pc.addTrack(track, local.current!));
    if (seat < peer) void offer(peer, pc);
    else signal(peer, "restart", {});
    return pc;
  }, [offer, seat, signal]);

  const handleSignal = useCallback(async (message: MediaSignal) => {
    const peer = message.from;
    if (!SEATS.includes(peer) || peer === seat || !mediaActive.current) return;
    const pc = ensurePeer(peer);
    if (!pc) return;
    try {
      if (message.kind === "offer") {
        if (pc.signalingState !== "stable") {
          // A higher-indexed seat never creates an initial offer, but renegotiation can race.
          await pc.setLocalDescription({ type: "rollback" });
        }
        await pc.setRemoteDescription(message.data as unknown as RTCSessionDescriptionInit);
        await pc.setLocalDescription(await pc.createAnswer());
        if (pc.localDescription) signal(peer, "answer", { type: "answer", sdp: pc.localDescription.sdp ?? "" });
      } else if (message.kind === "answer") {
        if (pc.signalingState === "have-local-offer") {
          await pc.setRemoteDescription(message.data as unknown as RTCSessionDescriptionInit);
        }
      } else if (message.kind === "ice") {
        const candidate = message.data as RTCIceCandidateInit;
        if (pc.remoteDescription) await pc.addIceCandidate(candidate);
        else pendingIce.current.set(peer, [...(pendingIce.current.get(peer) ?? []), candidate].slice(-32));
      } else if (seat < peer && pc.signalingState === "stable") {
        await offer(peer, pc);
      }
      if (pc.remoteDescription) {
        const queued = pendingIce.current.get(peer) ?? [];
        pendingIce.current.delete(peer);
        for (const candidate of queued) await pc.addIceCandidate(candidate);
      }
    } catch { setError("Ошибка согласования WebRTC. Проверь соединение или переподключи медиа."); }
  }, [ensurePeer, offer, seat, signal]);

  const stopLocalRecording = useCallback(() => {
    const resources = recordingResources.current;
    if (resources && resources.recorder.state !== "inactive") resources.recorder.stop();
  }, []);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    cursor.current = 0;
    async function poll() {
      try {
        const state = await getMedia(roomId, cursor.current);
        if (disposed) return;
        setPeers(Object.fromEntries(state.participants.map((p, i) => [i, p])));
        setRecording(state.recording);
        currentRecording.current = state.recording;
        // Refresh the watchdog only after the server confirms live consent
        // and all three current media participants.
        if (state.recording?.status === "active" &&
            state.recording.votes.every(v => v === true) &&
            state.participants.every(p => p.audio || p.video)) {
          confirmedAtMs.current = Date.now();
        }
        if (recordingResources.current && (
          state.recording?.status !== "active" ||
          state.participants.some(p => !p.audio && !p.video)
        )) stopLocalRecording();
        if (mediaActive.current) {
          for (const other of SEATS) {
            if (other !== seat && (state.participants[other].audio || state.participants[other].video)) {
              ensurePeer(other);
            }
          }
          for (const message of state.signals) await handleSignal(message);
        }
        // Firestore TTL may delete/recreate media/current with version 0.
        cursor.current = state.version;
      } catch {
        if (!disposed && recordingResources.current) {
          stopLocalRecording();
          setError("Запись остановлена: нет подтверждения согласий от сервера.");
        } else if (!disposed && mediaActive.current) {
          setError("Сигнализация временно недоступна. Игра продолжает работать.");
        }
      } finally {
        if (!disposed) {
          // Fast polling is only needed for a pending vote or active recording.
          const vote = currentRecording.current?.status;
          const intervalMs = vote === "requested" || vote === "ready" || vote === "active"
            ? 2500 : mediaActive.current ? 6000 : 12000;
          timer = setTimeout(poll, intervalMs);
        }
      }
    }
    void poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [roomId, seat, handleSignal, ensurePeer, stopLocalRecording, localVersion]);

  // Recording is fail-closed on connectivity loss, tab suspension and consent
  // expiry. JavaScript cannot promise instantaneous reaction while an OS is
  // frozen; real-device validation remains mandatory before production.
  useEffect(() => {
    const check = () => {
      if (!recordingResources.current) return;
      if (!recordingMayContinue(
        { recording: currentRecording.current, participants: Object.values(peers) },
        seat, confirmedAtMs.current, Date.now(),
        document.visibilityState === "visible" && navigator.onLine,
      )) {
        stopLocalRecording();
        setError("Запись остановлена: подтверждение согласий недоступно.");
      }
    };
    const clock = window.setInterval(check, 1_000);
    window.addEventListener("offline", check);
    document.addEventListener("visibilitychange", check);
    return () => {
      window.clearInterval(clock);
      window.removeEventListener("offline", check);
      document.removeEventListener("visibilitychange", check);
    };
  }, [peers, seat, stopLocalRecording]);

  // Presence uses a bounded per-seat idempotency marker, not a new Firestore operation document.
  useEffect(() => {
    if (!enabled.audio && !enabled.video) return;
    const heartbeat = setInterval(() => {
      void send("presence", { audio: enabled.audio, video: enabled.video })
        .catch(() => setError("Не удалось обновить присутствие в звонке."));
    }, 25000);
    return () => clearInterval(heartbeat);
  }, [enabled.audio, enabled.video, send]);

  const changeTrack = async (kind: "audio" | "video") => {
    setError("");
    try {
      const stream = local.current ?? new MediaStream();
      const existing = kind === "audio" ? stream.getAudioTracks() : stream.getVideoTracks();
      if (existing.length) {
        existing.forEach(track => { track.stop(); stream.removeTrack(track); });
      } else {
        const acquired = await navigator.mediaDevices.getUserMedia({ audio: kind === "audio", video: kind === "video" });
        acquired.getTracks().forEach(track => stream.addTrack(track));
      }
      local.current = stream;
      const next = { audio: stream.getAudioTracks().length > 0, video: stream.getVideoTracks().length > 0 };
      mediaActive.current = next.audio || next.video;
      setEnabled(next);
      disposeConnections();
      await send("presence", next);
      setLocalVersion(v => v + 1);
    } catch {
      setError("Не удалось включить устройство. Проверь разрешения камеры/микрофона и HTTPS.");
    }
  };

  const notifyPeersStop = () => {
    channels.current.forEach(channel => {
      if (channel.readyState === "open") channel.send("STOP");
    });
  };

  const recordCommand = async (action: "record_request" | "record_vote" | "record_stop", args = {}) => {
    try {
      if (action === "record_stop") {
        stopLocalRecording();
        notifyPeersStop();
      }
      await send(action, args);
    } catch { setError("Не удалось обновить согласие на запись."); }
  };

  const startRecording = async () => {
    if (!recording || recording.initiator !== seat || recording.status !== "ready") return;
    if (typeof MediaRecorder === "undefined" || !HTMLCanvasElement.prototype.captureStream) {
      setError("Локальная запись не поддерживается этим браузером.");
      return;
    }
    let resources: RecordingResources | null = null;
    try {
      const canvas = document.createElement("canvas");
      canvas.width = 1280;
      canvas.height = 720;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("No canvas context");
      const interval = setInterval(() => {
        const scene = sharedScene.current;
        ctx.fillStyle = "#162e27";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#e8cf99";
        ctx.font = "36px Georgia";
        ctx.fillText("Преферанс по-запорожски", 35, 48);
        ctx.font = "24px Georgia";
        ctx.fillText(`${scene.status} · ${scene.phase}`, 35, 93);
        const videos = Array.from(document.querySelectorAll<HTMLVideoElement>("[data-preferans-media-video]"));
        for (let i = 0; i < videos.length && i < 3; i++) {
          const video = videos[i];
          const x = 35 + i * 415;
          ctx.fillStyle = "#365346";
          ctx.fillRect(x, 125, 390, 300);
          if (video.readyState >= 2 && video.videoWidth) ctx.drawImage(video, x, 125, 390, 300);
        }
        ctx.fillStyle = "#e8cf99";
        ctx.font = "28px Georgia";
        ctx.fillText("Общий стол", 35, 475);
        ctx.font = "30px Georgia";
        ctx.fillText(scene.publicTrick.join("     ") || "Ожидание хода", 35, 528);
        ctx.font = "19px Georgia";
        ctx.fillText("Локальная запись · согласие всех трёх игроков", 35, 670);
      }, 70);
      const output = canvas.captureStream(15);
      const context = typeof AudioContext === "undefined" ? null : new AudioContext();
      if (context) {
        await context.resume();
        const destination = context.createMediaStreamDestination();
        for (const stream of [local.current, ...Object.values(remoteStreams.current)]) {
          if (stream?.getAudioTracks().length) context.createMediaStreamSource(stream).connect(destination);
        }
        destination.stream.getAudioTracks().forEach(track => output.addTrack(track));
      }
      const mime = recordMimes.find(type => MediaRecorder.isTypeSupported(type));
      const recorder = new MediaRecorder(output, mime ? { mimeType: mime } : undefined);
      resources = { recorder, stream: output, context, interval, chunks: [] };
      const active = resources;
      recorder.ondataavailable = event => { if (event.data.size) active.chunks.push(event.data); };
      recorder.onstop = () => {
        clearInterval(active.interval);
        active.stream.getTracks().forEach(track => track.stop());
        void active.context?.close();
        if (active.chunks.length) {
          const blob = new Blob(active.chunks, { type: recorder.mimeType || "video/webm" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `preferans-${recording.id}.${recorder.mimeType.includes("mp4") ? "mp4" : "webm"}`;
          a.click();
          setTimeout(() => URL.revokeObjectURL(url), 60000);
        }
        if (recordingResources.current === active) recordingResources.current = null;
      };
      await send("record_start");
      currentRecording.current = { ...recording, status: "active" };
      confirmedAtMs.current = Date.now();
      recordingResources.current = resources;
      recorder.start(1000);
      recorder.addEventListener("error", () => {
        stopLocalRecording();
        void send("record_stop").catch(() => undefined);
      });
    } catch {
      if (resources) {
        clearInterval(resources.interval);
        resources.stream.getTracks().forEach(track => track.stop());
        void resources.context?.close();
      }
      recordingResources.current = null;
      void send("record_stop").catch(() => undefined);
      setError("Не удалось создать запись. Согласие сброшено; проверь поддержку кодеков.");
    }
  };

  useEffect(() => () => {
    stopLocalRecording();
    connections.current.forEach(pc => pc.close());
    local.current?.getTracks().forEach(track => track.stop());
  }, [stopLocalRecording]);

  return <section className={styles.mediaPanel} aria-label="Медиа и локальная запись">
    <h2>Связь за столом</h2>
    <p>Камера и микрофон добровольны. Без них можно продолжать игру. Для прямой связи нужен WebRTC; некоторые сети без TURN могут её блокировать.</p>
    <div className={styles.buttons}>
      <button type="button" onClick={() => void changeTrack("audio")} aria-pressed={enabled.audio}>
        {enabled.audio ? "Выключить микрофон" : "Включить микрофон"}
      </button>
      <button type="button" onClick={() => void changeTrack("video")} aria-pressed={enabled.video}>
        {enabled.video ? "Выключить камеру" : "Включить камеру"}
      </button>
    </div>
    <div className={styles.videoGrid}>
      {SEATS.map(i => <VideoTile key={i} seat={i} muted={i === seat}
        stream={i === seat ? local.current : streams[i] ?? null} />)}
    </div>
    {recording?.status === "active" && <p className={styles.recordAlert} role="status">
      ИДЁТ ЗАПИСЬ — инициатор {label(recording.initiator)}. Видео сохраняется только на его устройстве.
    </p>}
    {recording?.status === "requested" && <div className={styles.consent}>
      <p>{label(recording.initiator)} предлагает локальную запись видео/голоса/открытого стола.</p>
      <p>Согласия: {recording.votes.map(v => v === true ? "Да" : v === false ? "Нет" : "Ожидание").join(" / ")}</p>
      {recording.votes[seat] === null && <div className={styles.buttons}>
        <button type="button" onClick={() => void recordCommand("record_vote", { approve: true })}>Согласен на запись</button>
        <button type="button" onClick={() => void recordCommand("record_vote", { approve: false })}>Не согласен</button>
      </div>}
    </div>}
    {recording?.status === "ready" && recording.initiator === seat &&
      <button type="button" onClick={() => void startRecording()}>Начать локальную запись</button>}
    {(!recording || recording.status === "stopped") && (enabled.audio || enabled.video) &&
      <button type="button" onClick={() => void recordCommand("record_request")}>Запросить согласие на запись</button>}
    {recording && ["requested", "ready", "active"].includes(recording.status) &&
      <button type="button" className={styles.stop} onClick={() => void recordCommand("record_stop")}>
        Отозвать согласие / остановить запись
      </button>}
    <p className={styles.footnote}>Запись содержит только общедоступный стол и разрешённые медиапотоки, не личные карты. Сервер не хранит аудио/видео. Участники видят статус записи. Отзыв согласия приходит через соединение и опрос сервера; мгновенная доставка при сбоях сети не гарантируется.</p>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <p className={styles.footnote}>Сейчас участвуют: {SEATS.filter(i => peers[i]?.audio || peers[i]?.video).length} из 3.</p>
  </section>;
}
