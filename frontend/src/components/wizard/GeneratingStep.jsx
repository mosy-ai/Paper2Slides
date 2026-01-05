import React from "react";
import { Loader2, CheckCircle } from "lucide-react";

const GeneratingStep = ({ stages, slides, onCancel }) => {
    const totalSlides = slides?.length || 0;
    const isGenerating = stages?.generate === "running";
    const isComplete = stages?.generate === "completed";

    // Calculate progress (approximate based on stages)
    const stagesComplete = Object.values(stages || {}).filter(
        (s) => s === "completed"
    ).length;
    const progressPercent = isComplete ? 100 : (stagesComplete / 4) * 100;

    return (
        <div className="flex-1 flex flex-col items-center justify-center p-8">
            <div className="w-full max-w-md text-center">
                {/* Progress Circle */}
                <div className="mb-8">
                    <div className="relative w-32 h-32 mx-auto">
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
                                className="text-blue-500"
                                strokeDasharray={`${progressPercent * 2.83} 283`}
                                transform="rotate(-90 50 50)"
                                style={{ transition: "stroke-dasharray 0.5s ease" }}
                            />
                        </svg>

                        {/* Center content */}
                        <div className="absolute inset-0 flex items-center justify-center">
                            {isComplete ? (
                                <CheckCircle className="w-12 h-12 text-green-500" />
                            ) : (
                                <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
                            )}
                        </div>
                    </div>
                </div>

                {/* Title */}
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                    {isComplete ? "Generation Complete!" : "Generating Slides..."}
                </h2>
                <p className="text-gray-600 dark:text-gray-400 mb-6">
                    {isComplete
                        ? "Your slides are ready"
                        : "Creating beautiful slides from your content"}
                </p>

                {/* Slide Preview Thumbnails (placeholder) */}
                {totalSlides > 0 && (
                    <div className="flex flex-wrap justify-center gap-2 mb-8">
                        {slides.slice(0, 8).map((slide, index) => (
                            <div
                                key={index}
                                className="w-16 h-12 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden"
                            >
                                {slide.image_url ? (
                                    <img
                                        src={slide.image_url}
                                        alt={`Slide ${index + 1}`}
                                        className="w-full h-full object-cover"
                                    />
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">
                                        {index + 1}
                                    </div>
                                )}
                            </div>
                        ))}
                        {totalSlides > 8 && (
                            <div className="w-16 h-12 bg-gray-100 dark:bg-gray-800 rounded-lg flex items-center justify-center text-xs text-gray-500">
                                +{totalSlides - 8}
                            </div>
                        )}
                    </div>
                )}

                {/* Progress Details */}
                <div className="space-y-2 text-sm text-gray-500 dark:text-gray-400">
                    {Object.entries(stages || {}).map(([stageId, status]) => (
                        <div
                            key={stageId}
                            className={`flex items-center justify-center gap-2 ${
                                status === "completed"
                                    ? "text-green-600 dark:text-green-400"
                                    : status === "running"
                                    ? "text-blue-600 dark:text-blue-400"
                                    : ""
                            }`}
                        >
                            {status === "completed" ? (
                                <CheckCircle className="w-3.5 h-3.5" />
                            ) : status === "running" ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                                <div className="w-3.5 h-3.5" />
                            )}
                            <span className="capitalize">{stageId}</span>
                        </div>
                    ))}
                </div>

                {/* Cancel Button */}
                {!isComplete && (
                    <button
                        onClick={onCancel}
                        className="mt-8 px-6 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                    >
                        Cancel
                    </button>
                )}
            </div>
        </div>
    );
};

export default GeneratingStep;
