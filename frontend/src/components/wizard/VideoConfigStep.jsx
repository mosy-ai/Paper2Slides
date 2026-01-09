import React, { useState } from "react";
import { Video, Play, ChevronLeft, Sparkles, Clock } from "lucide-react";

const VideoConfigStep = ({ slides, sessionId, onGenerate, onBack }) => {
    const [config, setConfig] = useState({
        voiceId: "default", // Uses configured default voice (MC anh duc)
        transitionDuration: 4, // Veo requires 4, 6, or 8 seconds
        transitionStyle: "ai_animated",
        resolution: "720p", // 720p for faster encoding
        language: "vi",
    });
    const [isGenerating, setIsGenerating] = useState(false);

    const handleGenerate = async () => {
        setIsGenerating(true);
        try {
            await onGenerate(config);
            // Note: onGenerate will change the step, so this component will unmount
        } catch (error) {
            console.error("Error starting video generation:", error);
        } finally {
            // Always reset in case we're still mounted (error case)
            setIsGenerating(false);
        }
    };

    // Estimate generation time and video length
    const totalSlides = slides?.length || 0;
    const estimatedGenTime = Math.ceil(totalSlides * 2); // ~2 min per slide
    const estimatedVideoLength = totalSlides * (30 + config.transitionDuration);

    const formatDuration = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.round(seconds % 60);
        return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
    };

    return (
        <div className="flex-1 flex flex-col overflow-hidden max-w-4xl mx-auto w-full">
            {/* Header */}
            <div className="flex-shrink-0 p-6 pb-0 mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <Video className="w-6 h-6 text-purple-500" />
                    <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                        Configure Video
                    </h2>
                </div>
                <p className="text-gray-600 dark:text-gray-400">
                    Generate a narrated video presentation from your slides
                </p>
            </div>

            <div className="flex-1 overflow-y-auto px-6 space-y-6">
                {/* Transition Settings */}
                <div className="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-2 mb-4">
                        <Sparkles className="w-5 h-5 text-purple-500" />
                        <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                            AI Transitions (Veo 3.1)
                        </h3>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Transition Style */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Transition Style
                            </label>
                            <select
                                value={config.transitionStyle}
                                onChange={(e) =>
                                    setConfig({ ...config, transitionStyle: e.target.value })
                                }
                                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            >
                                <option value="ai_animated">AI Animated (Veo 3.1)</option>
                                <option value="fade">Simple Fade</option>
                                <option value="slide">Slide</option>
                                <option value="none">No Transition</option>
                            </select>
                        </div>

                        {/* Transition Duration */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Transition Duration
                            </label>
                            <select
                                value={config.transitionDuration}
                                onChange={(e) =>
                                    setConfig({
                                        ...config,
                                        transitionDuration: parseFloat(e.target.value),
                                    })
                                }
                                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            >
                                <option value={4}>4 seconds (Fast)</option>
                                <option value={6}>6 seconds (Normal)</option>
                                <option value={8}>8 seconds (Cinematic)</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* Slides Preview */}
                <div className="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                            Slides to Include
                        </h3>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                            {totalSlides} slides
                        </span>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        {slides?.slice(0, 10).map((slide, index) => (
                            <div
                                key={index}
                                className="w-20 h-14 bg-gray-100 dark:bg-gray-700 rounded-lg overflow-hidden"
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
                        {totalSlides > 10 && (
                            <div className="w-20 h-14 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center text-xs text-gray-500">
                                +{totalSlides - 10}
                            </div>
                        )}
                    </div>
                </div>

                {/* Estimation */}
                <div className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-xl p-5 border border-purple-100 dark:border-purple-800">
                    <div className="flex items-center gap-2 mb-3">
                        <Clock className="w-5 h-5 text-purple-500" />
                        <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                            Estimated Output
                        </h3>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <div className="text-gray-500 dark:text-gray-400">
                                Generation Time
                            </div>
                            <div className="font-medium text-gray-900 dark:text-gray-100">
                                ~{estimatedGenTime} minutes
                            </div>
                        </div>
                        <div>
                            <div className="text-gray-500 dark:text-gray-400">Video Length</div>
                            <div className="font-medium text-gray-900 dark:text-gray-100">
                                ~{formatDuration(estimatedVideoLength)}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Actions */}
            <div className="flex-shrink-0 flex items-center justify-between p-6 pt-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
                <button
                    onClick={onBack}
                    className="flex items-center gap-2 px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                >
                    <ChevronLeft className="w-4 h-4" />
                    Back to Editor
                </button>

                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="flex items-center gap-2 px-6 py-2.5 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isGenerating ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                            Starting...
                        </>
                    ) : (
                        <>
                            <Play className="w-4 h-4" />
                            Generate Video
                        </>
                    )}
                </button>
            </div>
        </div>
    );
};

export default VideoConfigStep;
