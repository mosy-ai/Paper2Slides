import React from "react";
import { Loader2, CheckCircle, Circle, XCircle } from "lucide-react";

const STAGE_INFO = {
    rag: {
        name: "RAG Indexing",
        description: "Building knowledge graph from your document",
    },
    summary: {
        name: "Content Extraction",
        description: "Extracting and summarizing key content",
    },
    plan: {
        name: "Planning",
        description: "Creating slide structure and layout",
    },
    generate: {
        name: "Generation",
        description: "Generating slide images",
    },
};

const STAGE_ORDER = ["rag", "summary", "plan"];

const ProcessingStep = ({ stages, onCancel }) => {
    const getStageIcon = (status) => {
        switch (status) {
            case "completed":
                return <CheckCircle className="w-5 h-5 text-green-500" />;
            case "running":
                return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
            case "failed":
                return <XCircle className="w-5 h-5 text-red-500" />;
            default:
                return <Circle className="w-5 h-5 text-gray-300 dark:text-gray-600" />;
        }
    };

    const getStageLineColor = (status) => {
        switch (status) {
            case "completed":
                return "bg-green-500";
            case "running":
                return "bg-blue-500";
            default:
                return "bg-gray-200 dark:bg-gray-700";
        }
    };

    // Find current active stage
    const activeStage = STAGE_ORDER.find((s) => stages[s] === "running");
    const activeInfo = activeStage ? STAGE_INFO[activeStage] : null;

    return (
        <div className="flex-1 flex flex-col items-center justify-center p-8">
            <div className="w-full max-w-md text-center">
                {/* Animated Loader */}
                <div className="mb-8">
                    <div className="relative w-24 h-24 mx-auto">
                        <div className="absolute inset-0 rounded-full border-4 border-gray-200 dark:border-gray-700"></div>
                        <div className="absolute inset-0 rounded-full border-4 border-blue-500 border-t-transparent animate-spin"></div>
                        <div className="absolute inset-3 rounded-full bg-gray-50 dark:bg-gray-800 flex items-center justify-center">
                            <span className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                                {STAGE_ORDER.filter((s) => stages[s] === "completed").length}/{STAGE_ORDER.length}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Title */}
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                    Processing Your Document
                </h2>
                {activeInfo && (
                    <p className="text-gray-600 dark:text-gray-400 mb-8">
                        {activeInfo.description}...
                    </p>
                )}

                {/* Stage List */}
                <div className="space-y-4 text-left">
                    {STAGE_ORDER.map((stageId, index) => {
                        const info = STAGE_INFO[stageId];
                        const status = stages[stageId] || "pending";

                        return (
                            <div key={stageId} className="relative">
                                {/* Connection Line */}
                                {index < STAGE_ORDER.length - 1 && (
                                    <div
                                        className={`absolute left-[9px] top-8 w-0.5 h-8 ${getStageLineColor(
                                            status === "completed" ? "completed" : "pending"
                                        )}`}
                                    ></div>
                                )}

                                {/* Stage Item */}
                                <div className="flex items-start gap-3">
                                    <div className="flex-shrink-0 mt-0.5">
                                        {getStageIcon(status)}
                                    </div>
                                    <div className="flex-1">
                                        <p
                                            className={`font-medium ${
                                                status === "running"
                                                    ? "text-blue-600 dark:text-blue-400"
                                                    : status === "completed"
                                                    ? "text-gray-900 dark:text-gray-100"
                                                    : "text-gray-400 dark:text-gray-500"
                                            }`}
                                        >
                                            {info.name}
                                        </p>
                                        {status === "running" && (
                                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                                {info.description}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Cancel Button */}
                <button
                    onClick={onCancel}
                    className="mt-8 px-6 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                >
                    Cancel
                </button>
            </div>
        </div>
    );
};

export default ProcessingStep;
