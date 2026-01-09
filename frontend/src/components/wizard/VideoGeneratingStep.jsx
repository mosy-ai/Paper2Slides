import React, { useState, useEffect, useCallback } from "react";
import { Loader2, CheckCircle, XCircle, Video, Volume2, Sparkles, Film, Upload } from "lucide-react";

const STAGE_INFO = {
    script_generation: {
        label: "Script Generation",
        description: "Creating narration scripts",
        icon: Video,
    },
    narration: {
        label: "Narration",
        description: "Generating voice audio",
        icon: Volume2,
    },
    transitions: {
        label: "AI Transitions",
        description: "Creating smooth transitions",
        icon: Sparkles,
    },
    composition: {
        label: "Composition",
        description: "Composing video",
        icon: Film,
    },
    export: {
        label: "Export",
        description: "Finalizing video",
        icon: Upload,
    },
};

const VideoGeneratingStep = ({ sessionId, onComplete, onCancel }) => {
    const [videoState, setVideoState] = useState(null);
    const [error, setError] = useState(null);

    const pollStatus = useCallback(async () => {
        try {
            const response = await fetch(`/api/video/${sessionId}/status`);
            const data = await response.json();

            setVideoState(data);

            if (data.status === "completed") {
                // Fetch the final result
                const resultResponse = await fetch(`/api/video/${sessionId}/result`);
                const resultData = await resultResponse.json();
                onComplete(resultData);
                return true; // Stop polling
            } else if (data.status === "failed") {
                setError(data.error || "Video generation failed");
                return true; // Stop polling
            } else if (data.status === "cancelled") {
                setError("Video generation was cancelled");
                return true; // Stop polling
            }

            return false; // Continue polling
        } catch (err) {
            console.error("Error polling video status:", err);
            return false;
        }
    }, [sessionId, onComplete]);

    useEffect(() => {
        let intervalId;

        const startPolling = async () => {
            // Initial poll
            const shouldStop = await pollStatus();
            if (shouldStop) return;

            // Poll every 5 seconds
            intervalId = setInterval(async () => {
                const shouldStop = await pollStatus();
                if (shouldStop && intervalId) {
                    clearInterval(intervalId);
                }
            }, 5000);
        };

        startPolling();

        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [pollStatus]);

    const handleCancel = async () => {
        try {
            await fetch(`/api/video/${sessionId}/cancel`, { method: "POST" });
            onCancel();
        } catch (err) {
            console.error("Error cancelling video:", err);
        }
    };

    const progress = videoState?.progress || {};
    const stages = videoState?.stages || {};
    const percentage = progress.percentage || 0;
    const currentStage = progress.current_stage;
    const message = progress.message || "Preparing video generation...";

    const isComplete = videoState?.status === "completed";
    const isFailed = videoState?.status === "failed" || error;

    return (
        <div className="flex-1 flex flex-col items-center justify-center p-8">
            <div className="w-full max-w-lg text-center">
                {/* Progress Circle */}
                <div className="mb-8">
                    <div className="relative w-40 h-40 mx-auto">
                        {/* Background circle */}
                        <svg className="w-full h-full" viewBox="0 0 100 100">
                            <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="6"
                                className="text-gray-200 dark:text-gray-700"
                            />
                            {/* Progress circle */}
                            <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="6"
                                strokeLinecap="round"
                                className={`${
                                    isFailed
                                        ? "text-red-500"
                                        : isComplete
                                        ? "text-green-500"
                                        : "text-purple-500"
                                }`}
                                strokeDasharray={`${percentage * 2.83} 283`}
                                transform="rotate(-90 50 50)"
                                style={{ transition: "stroke-dasharray 0.5s ease" }}
                            />
                        </svg>

                        {/* Center content */}
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                            {isFailed ? (
                                <XCircle className="w-12 h-12 text-red-500" />
                            ) : isComplete ? (
                                <CheckCircle className="w-12 h-12 text-green-500" />
                            ) : (
                                <>
                                    <Video className="w-10 h-10 text-purple-500 mb-1" />
                                    <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
                                        {Math.round(percentage)}%
                                    </span>
                                </>
                            )}
                        </div>
                    </div>
                </div>

                {/* Title */}
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                    {isFailed
                        ? "Generation Failed"
                        : isComplete
                        ? "Video Ready!"
                        : "Generating Video..."}
                </h2>

                {/* Message */}
                <p className="text-gray-600 dark:text-gray-400 mb-6 min-h-[24px]">
                    {isFailed ? error : message}
                </p>

                {/* Current slide progress */}
                {progress.current_slide > 0 && progress.total_slides > 0 && !isComplete && (
                    <div className="text-sm text-gray-500 dark:text-gray-400 mb-6">
                        Processing slide {progress.current_slide} of {progress.total_slides}
                    </div>
                )}

                {/* Stage Progress */}
                <div className="space-y-3 mb-8">
                    {Object.entries(STAGE_INFO).map(([stageId, info]) => {
                        const status = stages[stageId];
                        const isCurrentStage = currentStage === stageId;
                        const StageIcon = info.icon;

                        return (
                            <div
                                key={stageId}
                                className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
                                    isCurrentStage
                                        ? "bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800"
                                        : status === "completed"
                                        ? "bg-green-50 dark:bg-green-900/10"
                                        : "bg-gray-50 dark:bg-gray-800/50"
                                }`}
                            >
                                {/* Status Icon */}
                                <div
                                    className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                        status === "completed"
                                            ? "bg-green-100 dark:bg-green-900/30"
                                            : status === "running"
                                            ? "bg-purple-100 dark:bg-purple-900/30"
                                            : status === "failed"
                                            ? "bg-red-100 dark:bg-red-900/30"
                                            : "bg-gray-100 dark:bg-gray-700"
                                    }`}
                                >
                                    {status === "completed" ? (
                                        <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
                                    ) : status === "running" ? (
                                        <Loader2 className="w-4 h-4 text-purple-600 dark:text-purple-400 animate-spin" />
                                    ) : status === "failed" ? (
                                        <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
                                    ) : (
                                        <StageIcon className="w-4 h-4 text-gray-400" />
                                    )}
                                </div>

                                {/* Stage Info */}
                                <div className="flex-1 text-left">
                                    <div
                                        className={`text-sm font-medium ${
                                            status === "completed"
                                                ? "text-green-700 dark:text-green-400"
                                                : status === "running"
                                                ? "text-purple-700 dark:text-purple-400"
                                                : "text-gray-600 dark:text-gray-400"
                                        }`}
                                    >
                                        {info.label}
                                    </div>
                                    <div className="text-xs text-gray-500 dark:text-gray-500">
                                        {info.description}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Cancel Button */}
                {!isComplete && !isFailed && (
                    <button
                        onClick={handleCancel}
                        className="px-6 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                    >
                        Cancel
                    </button>
                )}

                {/* Retry/Back on Error */}
                {isFailed && (
                    <button
                        onClick={onCancel}
                        className="px-6 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                    >
                        Back to Configuration
                    </button>
                )}
            </div>
        </div>
    );
};

export default VideoGeneratingStep;
