"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, ReactNode } from "react";
import clsx from "clsx";
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  Download,
  History,
  Home,
  RefreshCw,
  Share2,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { Variants } from "framer-motion";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";

type JobStatus = "queued" | "processing" | "completed" | "failed";
type Verdict = "Genuine" | "Suspicious" | "Likely Forged";
type FindingStatus = "pass" | "review" | "risk";
type ScanMode = "text" | "pdf" | "image" | "video" | "audio";
type AppView = "verify" | "history";

interface JobAcceptedResponse {
  job_id: string;
  status: JobStatus;
  result_url: string;
}

interface ModuleFinding {
  id: string;
  title: string;
  score: number;
  status: FindingStatus;
  summary: string;
  evidence: string[];
}

interface ForensicReport {
  job_id: string;
  filename: string;
  content_type: string;
  status: "completed";
  overall_score: number;
  verdict: Verdict;
  reasoning: string[];
  explanation?: string | null;
  findings: ModuleFinding[];
  heatmap?: string | null;
  created_at: string;
}

interface JobResultResponse {
  job_id: string;
  status: JobStatus;
  report?: ForensicReport | null;
  error?: string | null;
}

interface RecentScan {
  id: string;
  verdict: string;
  score: number;
  type: string;
  createdAt: string;
}

const navItems = [
  { id: "verify", label: "Scan", icon: Home },
  { id: "history", label: "Results", icon: History },
] as const;

const modeConfig = {
  text: {
    label: "Text",
    icon: "article",
    accent: "#ff571f",
    accept: ".txt,.md,text/plain,text/markdown",
    upload: "TXT, MD",
    action: "Analyze Text",
  },
  pdf: {
    label: "PDF",
    icon: "picture_as_pdf",
    accent: "#ffc107",
    accept: ".pdf,application/pdf",
    upload: "PDF",
    action: "Analyze PDF",
  },
  image: {
    label: "Image",
    icon: "image",
    accent: "#6ebc6b",
    accept: ".jpg,.jpeg,.png,image/png,image/jpeg",
    upload: "JPG, PNG",
    action: "Analyze Image",
  },
  video: {
    label: "Video",
    icon: "videocam",
    accent: "#1976d2",
    accept: ".mp4,.webm,.mov,.m4v,video/mp4,video/webm,video/quicktime",
    upload: "MP4, WEBM, MOV",
    action: "Analyze Video",
  },
  audio: {
    label: "Audio",
    icon: "mic",
    accent: "#98c0e3",
    accept: ".mp3,.wav,.m4a,audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/mp4,audio/x-m4a",
    upload: "MP3, WAV, M4A",
    action: "Analyze Audio",
  },
} satisfies Record<
  ScanMode,
  {
    label: string;
    icon: string;
    accent: string;
    accept: string;
    upload: string;
    action: string;
  }
>;

const chartColors = ["#be63dd", "#5792eb", "#ffbc5e", "#ff514d"];

const screenVariant: Variants = {
  hidden: { opacity: 1, y: 0 },
  show: { opacity: 1, y: 0, transition: { duration: 0 } },
  exit: { opacity: 1, y: 0, transition: { duration: 0 } },
};

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clampScore(score: number): number {
  return Math.max(0, Math.min(100, Number.isFinite(score) ? score : 0));
}

function displayVerdict(report: ForensicReport): string {
  const score = report.overall_score;
  const textLike = report.content_type === "text/plain" || report.content_type === "application/pdf";
  const audioLike = report.content_type.startsWith("audio/");
  const videoLike = report.content_type.startsWith("video/");

  if (score >= 75) {
    if (audioLike) return "Likely Voice-Altered";
    if (videoLike) return "Likely Video-Altered";
    return textLike ? "Likely AI-Generated" : "Likely AI-Altered";
  }

  if (score >= 40) return "Needs Review";
  return textLike ? "Likely Human" : "Likely Authentic";
}

function displayType(report: ForensicReport): string {
  if (report.content_type === "application/pdf") return "PDF Analysis";
  if (report.content_type.startsWith("audio/")) return "Voice Analysis";
  if (report.content_type.startsWith("video/")) return "Video Analysis";
  if (report.content_type.startsWith("image/")) return "Image Analysis";
  return "Text Analysis";
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "2-digit", day: "2-digit", year: "2-digit" });
}

function toInsight(finding: ModuleFinding) {
  const labels: Record<string, string> = {
    metadata: "Metadata",
    visual: "Visual",
    ai_generated: "Synthetic Signals",
    text_font: "Layout",
    security: "Security Cues",
    text_ai: "Semantic Pattern",
    embedded_images: "Embedded Image",
    video_ai: "Frame Signal",
    audio_ai: "Audio Signal",
  };

  return {
    id: finding.id,
    label: labels[finding.id] ?? finding.title,
    tone: finding.status,
    score: clampScore(finding.score),
    summary: finding.summary,
    evidence: finding.evidence,
  };
}

function moduleBars(findings: ModuleFinding[]) {
  return findings.slice(0, 4).map((finding, index) => ({
    label: toInsight(finding).label,
    score: clampScore(finding.score),
    color: chartColors[index % chartColors.length],
  }));
}

export default function HomePage() {
  const [view, setView] = useState<AppView>("verify");
  const [mode, setMode] = useState<ScanMode>("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [report, setReport] = useState<ForensicReport | null>(null);
  const [status, setStatus] = useState<JobStatus | "idle">("idle");
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [recentScans, setRecentScans] = useState<RecentScan[]>([]);
  const [analysisRun, setAnalysisRun] = useState(0);

  const isRunning = status === "queued" || status === "processing";
  const resultVerdict = report ? displayVerdict(report) : "";
  const resultType = report ? displayType(report) : "";
  const visibleFindings = useMemo(() => report?.findings.map(toInsight) ?? [], [report]);

  function resetFlow() {
    setReport(null);
    setStatus("idle");
    setError(null);
    setShowDetails(false);
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setText("");
    setView("verify");
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setReport(null);
    setError(null);

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (selected && selected.type.startsWith("image/")) {
      setPreviewUrl(URL.createObjectURL(selected));
    } else {
      setPreviewUrl(null);
    }
  }

  function onModeChange(nextMode: ScanMode) {
    setMode(nextMode);
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setReport(null);
    setError(null);
  }

  async function submitText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!text.trim()) {
      setError("Paste text before analysis.");
      setTimeout(() => setError(null), 4000);
      return;
    }

    const formData = new FormData();
    formData.append("text", text);
    formData.append("filename", "pasted-text.txt");
    await startAnalysis("/api/documents/analyze-text", formData);
  }

  async function submitFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a file before analysis.");
      setTimeout(() => setError(null), 4000);
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    await startAnalysis("/api/documents/analyze", formData);
  }

  async function startAnalysis(endpoint: string, formData: FormData) {
    setError(null);
    setReport(null);
    setShowDetails(false);
    setStatus("queued");
    setAnalysisRun((run) => run + 1);

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let msg = "Analysis could not start.";
        try {
          const payload = await response.json();
          if (payload?.detail) msg = payload.detail;
        } catch {
          // Keep the readable fallback when the backend returns non-JSON.
        }
        throw new Error(msg);
      }

      const accepted = (await response.json()) as JobAcceptedResponse;
      await pollForReport(accepted.result_url);
    } catch (err) {
      setStatus("failed");
      setError(err instanceof Error ? err.message : "Analysis failed.");
      setTimeout(() => setError(null), 5000);
    }
  }

  async function pollForReport(resultUrl: string) {
    for (let attempt = 0; attempt < 45; attempt += 1) {
      await wait(attempt === 0 ? 450 : 1200);
      const response = await fetch(resultUrl);
      if (!response.ok) {
        throw new Error("Could not fetch the result.");
      }

      const payload = (await response.json()) as JobResultResponse;
      setStatus(payload.status);

      if (payload.status === "completed" && payload.report) {
        setReport(payload.report);
        setRecentScans((items) =>
          [
            {
              id: payload.report!.job_id,
              verdict: displayVerdict(payload.report!),
              score: payload.report!.overall_score,
              type: displayType(payload.report!),
              createdAt: payload.report!.created_at,
            },
            ...items,
          ].slice(0, 8),
        );
        return;
      }

      if (payload.status === "failed") {
        throw new Error(payload.error || "Analysis job failed.");
      }
    }

    throw new Error("Analysis took too long. Try a smaller file.");
  }

  async function shareResult() {
    if (!report) return;

    const shareText = `Verification result: ${resultVerdict} (${report.overall_score.toFixed(
      1,
    )}% AI probability). Job ${report.job_id.slice(0, 8)}.`;
    const nav = window.navigator as Navigator & {
      share?: (data: ShareData) => Promise<void>;
      clipboard?: Clipboard;
    };

    if (nav.share) {
      await nav.share({ title: "Verification Result", text: shareText });
      return;
    }

    if (nav.clipboard) {
      await nav.clipboard.writeText(shareText);
    }
  }

  return (
    <main className="min-h-dvh overflow-hidden bg-[#101011] text-[#ededed]">
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -28, x: "-50%" }}
            animate={{ opacity: 1, y: 8, x: "-50%" }}
            exit={{ opacity: 0, y: -28, x: "-50%" }}
            className="fixed left-1/2 top-3 z-50 max-w-[calc(100%-24px)] rounded-full border border-[#ff514d]/60 bg-[#151516] px-5 py-3 text-center text-[11px] font-black uppercase tracking-[0.14em] text-[#ff514d] shadow-2xl"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      <section className="relative flex min-h-dvh w-full max-w-[390px] flex-col overflow-hidden px-5 pb-5 pt-6 md:mx-auto">
        <AppHeader />

        <div className="phone-scroll flex-1 overflow-y-auto overflow-x-hidden pb-24 pt-7">
          <AnimatePresence mode="wait">
            {view === "verify" && report ? (
              <ResultScreen
                key="result"
                report={report}
                verdict={resultVerdict}
                resultType={resultType}
                insights={visibleFindings}
                showDetails={showDetails}
                onBack={resetFlow}
                onToggleDetails={() => setShowDetails((value) => !value)}
                onShare={shareResult}
                onAnalyzeAnother={resetFlow}
              />
            ) : view === "verify" ? (
              <ScanScreen
                key="scan"
                mode={mode}
                text={text}
                file={file}
                previewUrl={previewUrl}
                recentScans={recentScans}
                isRunning={isRunning}
                onModeChange={onModeChange}
                onTextChange={setText}
                onFileChange={onFileChange}
                onSubmitText={submitText}
                onSubmitFile={submitFile}
              />
            ) : (
              <HistoryScreen key="history" scans={recentScans} />
            )}
          </AnimatePresence>
        </div>

        <BottomNav view={view} onChange={setView} />
      </section>

      <AnimatePresence>
        {isRunning && <AnalyzingOverlay key={`${analysisRun}-${mode}`} mode={mode} />}
      </AnimatePresence>
    </main>
  );
}

function AppHeader() {
  return (
    <header className="shrink-0">
      <div className="flex items-center gap-1.5">
        <span aria-hidden="true" className="text-[17px] leading-none text-[#ededed]">
          ✳
        </span>
        <p
          className="text-[15px] font-semibold leading-none tracking-[-0.01em] text-[#ededed]"
          style={{
            fontFamily:
              '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", system-ui, sans-serif',
          }}
        >
          StarBusterLabs
        </p>
      </div>
    </header>
  );
}

function ScanScreen({
  mode,
  text,
  file,
  previewUrl,
  recentScans,
  isRunning,
  onModeChange,
  onTextChange,
  onFileChange,
  onSubmitText,
  onSubmitFile,
}: {
  mode: ScanMode;
  text: string;
  file: File | null;
  previewUrl: string | null;
  recentScans: RecentScan[];
  isRunning: boolean;
  onModeChange: (mode: ScanMode) => void;
  onTextChange: (value: string) => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSubmitText: (event: FormEvent<HTMLFormElement>) => void;
  onSubmitFile: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const current = modeConfig[mode];

  return (
    <motion.div variants={screenVariant} initial="hidden" animate="show" exit="exit" className="space-y-5">
      <section>
        <h1 className="max-w-[8.7ch] text-[2.55rem] font-medium leading-[0.98] tracking-normal text-[#ededed]">
          Authenticity Scanner
        </h1>
      </section>

      <ModePicker mode={mode} onModeChange={onModeChange} />

      <section className="rounded-[30px] bg-[#F9F6EE] p-4 text-[#080809]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-black/45">{current.label} mode</p>
            <h2 className="mt-1 text-2xl font-medium leading-none">Content Intake</h2>
          </div>
          <span
            className="grid h-12 w-12 shrink-0 place-items-center rounded-full text-[#ededed] shadow-sm"
            style={{ backgroundColor: current.accent }}
            aria-hidden="true"
          >
            <MaterialIcon alt={`${current.label} icon`} color="#ffffff" size={24} name={current.icon} />
          </span>
        </div>

        <div className="mt-4">
          {mode === "text" ? (
            <form className="space-y-3" onSubmit={onSubmitText}>
              <textarea
                value={text}
                onChange={(event) => onTextChange(event.target.value)}
                placeholder="Paste text for analysis..."
                aria-label="Text to scan"
                className="min-h-56 w-full resize-none rounded-[24px] border-0 bg-[#101011] p-4 text-sm leading-5 text-[#ededed] outline-none placeholder:text-white/35 focus:ring-2 focus:ring-[#ff514d]"
              />
              <ActionButton
                accent={current.accent}
                disabled={isRunning}
                icon={<MaterialIcon alt="" color="#ffffff" size={18} name="search" />}
                label={current.action}
              />
            </form>
          ) : (
            <form className="space-y-3" onSubmit={onSubmitFile}>
              <label className="relative flex min-h-64 cursor-pointer flex-col items-center justify-center overflow-hidden rounded-[24px] border border-dashed border-black/15 bg-[#101011] p-4 text-center text-[#ededed] transition hover:bg-[#19191b]">
                <input type="file" accept={current.accept} onChange={onFileChange} className="hidden" />
                {previewUrl ? (
                  <img src={previewUrl} alt="Selected preview" className="absolute inset-0 h-full w-full object-cover" />
                ) : (
                  <span
                    className="grid h-20 w-20 place-items-center rounded-full"
                    style={{ backgroundColor: current.accent }}
                    aria-hidden="true"
                  >
                    <MaterialIcon alt="" color="#ffffff" size={34} name="cloud_upload" />
                  </span>
                )}
                <span className="relative mt-4 max-w-full rounded-full bg-white px-4 py-2 text-xs font-bold text-black">
                  {file ? file.name : current.upload}
                </span>
              </label>
              <ActionButton
                accent={current.accent}
                disabled={isRunning}
                icon={<MaterialIcon alt="" color="#ffffff" size={18} name="cloud_upload" />}
                label={current.action}
              />
            </form>
          )}
        </div>
      </section>

      <RecentActivity scans={recentScans} />
    </motion.div>
  );
}

function ModePicker({ mode, onModeChange }: { mode: ScanMode; onModeChange: (mode: ScanMode) => void }) {
  return (
    <section className="grid grid-cols-5 gap-2">
      {(["text", "pdf", "image", "video", "audio"] as const).map((item) => {
        const config = modeConfig[item];
        const active = mode === item;
        return (
          <motion.button
            key={item}
            type="button"
            onClick={() => onModeChange(item)}
            className="grid min-h-[76px] place-items-center gap-1 px-0 text-[10px] font-bold transition"
            aria-pressed={active}
            whileTap={{ scale: 0.92 }}
            whileHover={{ y: -1 }}
            transition={{ type: "spring", stiffness: 400, damping: 22 }}
          >
            <motion.span
              className="grid h-14 w-14 place-items-center rounded-full"
              style={{ backgroundColor: config.accent }}
              animate={{
                boxShadow: active ? `0 0 0 4px ${config.accent}24` : "0 0 0 0px transparent",
                opacity: active ? 1 : 0.74,
                y: active ? -2 : 0,
                scale: active ? 1.06 : 1,
              }}
              transition={{ type: "spring", stiffness: 380, damping: 20 }}
            >
              <MaterialIcon alt="" color="#ffffff" size={22} name={config.icon} />
            </motion.span>
            <span style={{ color: active ? config.accent : "rgba(255,255,255,0.58)" }}>{config.label}</span>
          </motion.button>
        );
      })}
    </section>
  );
}

function MaterialIcon({
  name,
  color,
  size = 24,
  alt,
  fill = true,
  weight = 500,
}: {
  name: string;
  color?: string;
  size?: number;
  alt?: string;
  fill?: boolean;
  weight?: number;
}) {
  return (
    <span
      className="material-symbols-rounded block shrink-0"
      aria-label={alt || undefined}
      aria-hidden={alt ? undefined : true}
      role={alt ? "img" : undefined}
      style={{
        fontSize: size,
        width: size,
        height: size,
        color,
        fontVariationSettings: `"FILL" ${fill ? 1 : 0}, "wght" ${weight}, "GRAD" 0, "opsz" ${size}`,
      }}
    >
      {name}
    </span>
  );
}

function ActionButton({
  accent,
  icon,
  label,
  disabled,
}: {
  accent: string;
  icon: ReactNode;
  label: string;
  disabled: boolean;
}) {
  return (
    <motion.button
      type="submit"
      disabled={disabled}
      whileTap={{ scale: 0.97 }}
      whileHover={disabled ? undefined : { scale: 1.01 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className="flex h-[52px] w-full items-center justify-center gap-2 rounded-full px-5 py-4 text-xs font-black uppercase tracking-[0.12em] text-[#ededed]"
      style={{ backgroundColor: accent }}
    >
      {icon}
      {label}
    </motion.button>
  );
}

function ResultScreen({
  report,
  verdict,
  resultType,
  insights,
  showDetails,
  onBack,
  onToggleDetails,
  onShare,
  onAnalyzeAnother,
}: {
  report: ForensicReport;
  verdict: string;
  resultType: string;
  insights: ReturnType<typeof toInsight>[];
  showDetails: boolean;
  onBack: () => void;
  onToggleDetails: () => void;
  onShare: () => void;
  onAnalyzeAnother: () => void;
}) {
  const bentoRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const score = clampScore(report.overall_score);
  const bars = moduleBars(report.findings);
  const hasEvidence = insights.some((finding) => finding.evidence.length > 0);

  async function handleExportPDF() {
    if (!bentoRef.current) return;
    setIsExporting(true);
    try {
      const canvas = await html2canvas(bentoRef.current, { backgroundColor: "#101011", scale: 2 });
      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({ orientation: "portrait", unit: "px", format: [canvas.width, canvas.height] });
      pdf.addImage(imgData, "PNG", 0, 0, canvas.width, canvas.height);
      pdf.save(`forensic-report-${report.job_id.slice(0, 6)}.pdf`);
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <motion.div
      variants={screenVariant}
      initial="hidden"
      animate="show"
      exit="exit"
      ref={bentoRef}
      className="space-y-5"
    >
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to scanner"
          className="grid h-12 w-12 place-items-center rounded-full bg-[#242528] text-[#ededed]"
        >
          <ArrowLeft size={18} />
        </button>
        <button
          type="button"
          onClick={handleExportPDF}
          disabled={isExporting}
          className="flex h-12 items-center gap-2 rounded-full bg-[#242528] px-4 text-[10px] font-black uppercase tracking-[0.12em] text-white/85"
        >
          <Download size={15} />
          {isExporting ? "Saving" : "PDF"}
        </button>
      </div>

      <section>
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-white/38">{resultType}</p>
        <h1 className="mt-2 max-w-[8ch] text-[2.65rem] font-medium leading-[0.98] tracking-normal text-[#ededed]">
          Detailed Analysis
        </h1>
      </section>

      <section className="grid grid-cols-2 gap-3">
        <RiskPill label="AI Risk" value={`${score.toFixed(0)}%`} fill={score} color="#ff514d" />
        <RiskPill label="Confidence" value={`${Math.max(0, 100 - score).toFixed(0)}%`} fill={100 - score} striped />
      </section>

      <DonutScore score={score} verdict={verdict} />
      {bars.length > 0 && <BarStack bars={bars} />}

      {report.explanation && (
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="rounded-[26px] bg-[#1c1d1f] p-5"
        >
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-[#ffbc5e]/15">
              <MaterialIcon name="auto_awesome" color="#ffbc5e" size={18} />
            </span>
            <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">
              AI Assessment
            </h2>
          </div>
          <p className="mt-3 text-[15px] leading-6 text-white/85">{report.explanation}</p>
        </motion.section>
      )}

      {report.heatmap && (
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut", delay: 0.05 }}
          className="space-y-3 rounded-[26px] bg-[#1c1d1f] p-5"
        >
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-[#ff514d]/15">
              <MaterialIcon name="my_location" color="#ff514d" size={18} />
            </span>
            <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">
              Altered Regions
            </h2>
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={report.heatmap}
            alt="Heatmap highlighting regions with the strongest manipulation signals"
            className="w-full rounded-[18px] border border-white/5"
          />
          <p className="text-xs leading-5 text-white/45">
            Warmer areas show where the detector found the strongest signs of editing or synthesis.
          </p>
        </motion.section>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-medium text-[#ededed]">Signals</h2>
          {hasEvidence && (
            <button
              type="button"
              onClick={onToggleDetails}
              className="rounded-full bg-white/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] text-white/65"
            >
              {showDetails ? "Compact" : "Details"}
            </button>
          )}
        </div>
        <div className="space-y-2.5">
          {insights.length ? (
            insights.map((finding, idx) => (
              <FindingRow key={finding.id} finding={finding} showDetails={showDetails} index={idx} />
            ))
          ) : (
            <EmptyPanel title="No module details" copy="The backend returned a score without module evidence." />
          )}
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3">
        <motion.button
          type="button"
          onClick={onShare}
          whileTap={{ scale: 0.97 }}
          whileHover={{ scale: 1.01 }}
          transition={{ type: "spring", stiffness: 400, damping: 25 }}
          className="flex h-[52px] items-center justify-center gap-2 rounded-full bg-[#F9F6EE] px-4 py-4 text-xs font-black uppercase tracking-[0.12em] text-black"
        >
          <Share2 size={16} />
          Share
        </motion.button>
        <motion.button
          type="button"
          onClick={onAnalyzeAnother}
          whileTap={{ scale: 0.97 }}
          whileHover={{ scale: 1.01 }}
          transition={{ type: "spring", stiffness: 400, damping: 25 }}
          className="flex h-[52px] items-center justify-center gap-2 rounded-full bg-[#ff514d] px-4 py-4 text-xs font-black uppercase tracking-[0.12em] text-[#ededed]"
        >
          <RefreshCw size={16} />
          Rescan
        </motion.button>
      </div>
    </motion.div>
  );
}

function RiskPill({
  label,
  value,
  fill,
  color = "#ff514d",
  striped = false,
}: {
  label: string;
  value: string;
  fill: number;
  color?: string;
  striped?: boolean;
}) {
  return (
    <article className="rounded-[24px] border-l border-white/30 pl-3">
      <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-white/45">{label}</p>
      <strong className="mt-1 block font-mono text-2xl font-bold tracking-tight text-[#ededed]">{value}</strong>
      <div className="mt-3 h-16 overflow-hidden rounded-[22px] bg-white/10">
        <div
          className={clsx("h-full rounded-[22px]", striped && "stripe-fill")}
          style={{
            width: `${Math.max(12, Math.min(100, fill))}%`,
            backgroundColor: striped ? "transparent" : color,
          }}
        />
      </div>
    </article>
  );
}

function DonutScore({ score, verdict }: { score: number; verdict: string }) {
  const [shown, setShown] = useState(0);

  // Count the percentage up on mount for a premium reveal.
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const duration = 900;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(score * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [score]);

  const ring = `conic-gradient(#ff514d 0 ${shown}%, #be63dd ${shown}% ${Math.min(
    100,
    shown + 18,
  )}%, rgba(87,146,235,0.42) ${Math.min(100, shown + 18)}% 100%)`;

  return (
    <section className="grid place-items-center rounded-[34px] bg-[#0b0b0c] px-4 py-6">
      <motion.div
        initial={{ scale: 0.92, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 20 }}
        className="grid h-60 w-60 place-items-center rounded-full p-5"
        style={{ background: ring }}
      >
        <div className="grid h-full w-full place-items-center rounded-full bg-[#101011] text-center">
          <div>
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-white/45">AI Probability</p>
            <strong className="mt-2 block font-mono text-4xl font-bold tabular-nums tracking-tight text-[#ededed]">
              {shown.toFixed(0)}%
            </strong>
            <p className="mx-auto mt-2 max-w-[11rem] text-xs leading-4 text-white/55">{verdict}</p>
          </div>
        </div>
      </motion.div>
    </section>
  );
}

function BarStack({ bars }: { bars: { label: string; score: number; color: string }[] }) {
  return (
    <section className="rounded-[34px] bg-[#0b0b0c] p-4">
      <div className="grid h-56 grid-cols-4 items-end gap-3">
        {bars.map((bar, idx) => (
          <div key={bar.label} className="flex h-full flex-col justify-end gap-2">
            <motion.div
              className="min-h-8 rounded-[18px]"
              style={{ backgroundColor: bar.color }}
              initial={{ height: "8%", opacity: 0.5 }}
              animate={{ height: `${Math.max(12, Math.min(100, bar.score))}%`, opacity: 1 }}
              transition={{ type: "spring", stiffness: 120, damping: 18, delay: idx * 0.08 }}
            />
            <div className="stripe-fill h-16 rounded-[18px] opacity-55" style={{ color: bar.color }} />
          </div>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-4 gap-3 text-center font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-white/62">
        {bars.map((bar) => (
          <span key={bar.label} className="truncate">
            {bar.label}
          </span>
        ))}
      </div>
    </section>
  );
}

function FindingRow({
  finding,
  showDetails,
  index = 0,
}: {
  finding: ReturnType<typeof toInsight>;
  showDetails: boolean;
  index?: number;
}) {
  const StatusIcon =
    finding.tone === "risk" ? AlertTriangle : finding.tone === "review" ? RefreshCw : CheckCircle2;
  const sign = finding.tone === "risk" ? "+" : finding.tone === "review" ? "~" : "-";

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut", delay: Math.min(index * 0.06, 0.4) }}
      className="rounded-[24px] bg-[#F9F6EE] p-2.5 text-black"
    >
      <div className="flex items-center gap-3">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[#101011] text-[#ededed]">
          <StatusIcon size={19} strokeWidth={2.2} />
        </span>
        <div className="min-w-0 flex-1">
          <strong className="block truncate text-sm font-semibold">{finding.label}</strong>
          <p className="mt-0.5 text-xs font-medium text-black/45">{finding.summary}</p>
        </div>
        <span className="shrink-0 font-mono text-sm font-bold">
          {sign} {finding.score.toFixed(0)}
        </span>
      </div>
      <AnimatePresence initial={false}>
        {showDetails && finding.evidence.length > 0 && (
          <motion.ul
            initial={{ opacity: 0, height: 0, marginTop: 0 }}
            animate={{ opacity: 1, height: "auto", marginTop: 12 }}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="space-y-1 overflow-hidden rounded-[18px] bg-white px-4 py-3 text-xs leading-5 text-black/60"
          >
            {finding.evidence.slice(0, 3).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </motion.article>
  );
}

function RecentActivity({ scans }: { scans: RecentScan[] }) {
  if (!scans.length) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-[#ededed]">Session Results</h2>
        <span className="text-xs font-semibold text-white/40">{scans.length}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1 [scrollbar-width:none]">
        {scans.map((scan) => (
          <article key={scan.id} className="min-w-36 rounded-[24px] bg-[#242528] p-4">
            <p className="truncate font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-white/40">{scan.type}</p>
            <strong className="mt-4 block font-mono text-3xl font-bold tracking-tight text-[#ededed]">{scan.score.toFixed(0)}%</strong>
            <p className="mt-2 font-mono text-xs text-white/45">{formatDate(scan.createdAt)}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function HistoryScreen({ scans }: { scans: RecentScan[] }) {
  return (
    <motion.div variants={screenVariant} initial="hidden" animate="show" exit="exit" className="space-y-5">
      <section>
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-white/38">Current Session</p>
        <h1 className="mt-2 max-w-[8ch] text-[2.65rem] font-medium leading-[0.98] tracking-normal text-[#ededed]">
          Analysis Results
        </h1>
      </section>

      {scans.length ? (
        <div className="space-y-3">
          {scans.map((scan) => (
            <article key={scan.id} className="rounded-[24px] bg-[#F9F6EE] p-2.5 text-black">
              <div className="flex items-center gap-3">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[#101011] text-[#ededed]">
                  <BarChart3 size={19} />
                </span>
                <div className="min-w-0 flex-1">
                  <strong className="block truncate text-sm font-semibold">{scan.verdict}</strong>
                  <p className="mt-0.5 font-mono text-xs font-medium text-black/45">{formatDate(scan.createdAt)}</p>
                </div>
                <span className="shrink-0 font-mono text-lg font-bold">{scan.score.toFixed(0)}%</span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyPanel title="No results yet" copy="Completed scans will appear here for this browser session." />
      )}
    </motion.div>
  );
}

function EmptyPanel({ title, copy }: { title: string; copy: string }) {
  return (
    <section className="rounded-[30px] bg-[#F9F6EE] p-5 text-black">
      <h2 className="text-2xl font-medium leading-none">{title}</h2>
      <p className="mt-3 text-sm leading-5 text-black/55">{copy}</p>
    </section>
  );
}

function BottomNav({ view, onChange }: { view: AppView; onChange: (view: AppView) => void }) {
  return (
    <nav className="absolute bottom-5 left-5 right-5 z-20 rounded-full bg-black p-2 shadow-2xl">
      <div className="grid grid-cols-2 gap-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = view === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={clsx(
                "relative flex h-12 items-center justify-center rounded-full text-white/70 transition",
                active && "text-[#ededed]",
              )}
              aria-label={item.label}
            >
              {active && (
                <motion.span
                  layoutId="bottom-nav"
                  className="absolute inset-0 rounded-full bg-[#ff514d]"
                  transition={{ type: "spring", stiffness: 420, damping: 32 }}
                />
              )}
              <span className="relative z-10 flex items-center gap-2">
                <Icon size={17} strokeWidth={2.3} aria-hidden="true" />
                <span className="text-xs font-semibold">{item.label}</span>
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

function AnalyzingOverlay({ mode }: { mode: ScanMode }) {
  const [showLongMedia, setShowLongMedia] = useState(false);
  const [progress, setProgress] = useState(4);

  useEffect(() => {
    if (mode !== "video" && mode !== "audio") return;
    const timer = window.setTimeout(() => setShowLongMedia(true), 3000);
    return () => window.clearTimeout(timer);
  }, [mode]);

  // Simulated progress: eases toward ~95% while the backend works, never
  // hitting 100 until the job actually completes and the overlay unmounts.
  useEffect(() => {
    const id = window.setInterval(() => {
      setProgress((prev) => {
        if (prev >= 95) return 95;
        const step = prev < 60 ? 4.5 : prev < 85 ? 1.6 : 0.5;
        return Math.min(95, prev + step);
      });
    }, 220);
    return () => window.clearInterval(id);
  }, []);

  const rounded = Math.round(progress);

  // Five brand colors, applied as a smooth SVG gradient stroke (rounded caps,
  // anti-aliased edges) over a faint track — a single ring, no stacking.
  const brand = ["#ff571f", "#ffc107", "#6ebc6b", "#1976d2", "#98c0e3"];
  const R = 52;
  const C = 2 * Math.PI * R;
  const dash = (rounded / 100) * C;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      className="fixed inset-0 z-40 grid place-items-center bg-[#0b0b0c]/95 px-6 text-center text-[#ededed] backdrop-blur-md"
    >
      <div className="flex flex-col items-center">
        <div className="relative grid h-36 w-36 place-items-center">
          <svg
            viewBox="0 0 120 120"
            className="h-full w-full -rotate-90"
            style={{ filter: "drop-shadow(0 0 14px rgba(118,150,235,0.35))" }}
          >
            <defs>
              <linearGradient id="loadGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                {brand.map((c, i) => (
                  <stop key={c} offset={`${(i / (brand.length - 1)) * 100}%`} stopColor={c} />
                ))}
              </linearGradient>
            </defs>
            <circle cx="60" cy="60" r={R} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="6" />
            <motion.circle
              cx="60"
              cy="60"
              r={R}
              fill="none"
              stroke="url(#loadGrad)"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={C}
              animate={{ strokeDashoffset: C - dash }}
              transition={{ type: "spring", stiffness: 90, damping: 20 }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
            <motion.span
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
            >
              <MaterialIcon alt="Scanning" color="#ffffff" size={22} name="search" />
            </motion.span>
            <span className="font-mono text-xl font-bold tabular-nums tracking-tight text-[#ededed]">{rounded}%</span>
          </div>
        </div>

        <h2 className="mt-8 text-2xl font-medium tracking-tight text-[#ededed]">Analyzing</h2>
        <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.22em] text-white/40">
          {showLongMedia ? "Large media — hang tight" : "Running forensic checks"}
        </p>

        {/* Five-dot brand strip for a minimal Google touch */}
        <div className="mt-6 flex items-center gap-2">
          {brand.map((c, i) => (
            <motion.span
              key={c}
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: c }}
              animate={{ opacity: [0.25, 1, 0.25], y: [0, -3, 0] }}
              transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut", delay: i * 0.12 }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  );
}
