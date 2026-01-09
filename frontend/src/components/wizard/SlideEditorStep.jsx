import React, { useState, useCallback, useRef } from "react";
import {
    ChevronLeft,
    ChevronRight,
    Download,
    RefreshCw,
    Upload,
    X,
    Loader2,
    Presentation,
    Video,
} from "lucide-react";

const SlideEditorStep = ({
    slides,
    sessionId,
    onRegenerateSlide,
    onGenerateVideo,
    videoUrl,
    error,
}) => {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [editPrompt, setEditPrompt] = useState("");
    const [referenceImage, setReferenceImage] = useState(null);
    const [referencePreview, setReferencePreview] = useState(null);
    const [isRegenerating, setIsRegenerating] = useState(false);
    const [regenerateError, setRegenerateError] = useState(null);
    const fileInputRef = useRef(null);

    const currentSlide = slides[currentIndex];
    const totalSlides = slides.length;

    // Navigation
    const goToPrevious = useCallback(() => {
        setCurrentIndex((prev) => Math.max(0, prev - 1));
    }, []);

    const goToNext = useCallback(() => {
        setCurrentIndex((prev) => Math.min(totalSlides - 1, prev + 1));
    }, [totalSlides]);

    const goToSlide = useCallback((index) => {
        setCurrentIndex(index);
    }, []);

    // Handle reference image upload
    const handleImageUpload = useCallback((e) => {
        const file = e.target.files?.[0];
        if (file) {
            setReferenceImage(file);
            const reader = new FileReader();
            reader.onload = (e) => {
                setReferencePreview(e.target.result);
            };
            reader.readAsDataURL(file);
        }
    }, []);

    const clearReferenceImage = useCallback(() => {
        setReferenceImage(null);
        setReferencePreview(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    }, []);

    // Handle regeneration
    const handleRegenerate = useCallback(async () => {
        if (!editPrompt.trim() && !referenceImage) {
            setRegenerateError("Please enter a prompt or upload a reference image");
            return;
        }

        setIsRegenerating(true);
        setRegenerateError(null);

        try {
            await onRegenerateSlide(currentIndex, editPrompt, referenceImage);

            // Clear form after success
            setEditPrompt("");
            clearReferenceImage();
        } catch (err) {
            setRegenerateError(err.message);
        } finally {
            setIsRegenerating(false);
        }
    }, [currentIndex, editPrompt, referenceImage, onRegenerateSlide, clearReferenceImage]);

    // Get download URL
    const getDownloadUrl = () => {
        // Find the PDF URL from the first slide's path
        if (slides.length > 0 && slides[0].image_url) {
            const pathParts = slides[0].image_url.split("/");
            pathParts.pop(); // Remove slide file
            return `${pathParts.join("/")}/slides.pdf`;
        }
        return null;
    };

    return (
        <div className="flex-1 flex overflow-hidden">
            {/* Main Slide Area */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
                            <Presentation className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                                Your Slides
                            </h2>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                {totalSlides} slides generated
                            </p>
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-3">
                        {/* Generate Video Button - only show if no video exists */}
                        {onGenerateVideo && !videoUrl && (
                            <button
                                onClick={onGenerateVideo}
                                className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-all"
                            >
                                <Video className="w-4 h-4" />
                                Generate Video
                            </button>
                        )}

                        {/* Download Video Button - show if video exists */}
                        {videoUrl && (
                            <a
                                href={videoUrl}
                                download
                                className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-all"
                            >
                                <Download className="w-4 h-4" />
                                Download Video
                            </a>
                        )}

                        {/* Download PDF Button */}
                        {getDownloadUrl() && (
                            <a
                                href={getDownloadUrl()}
                                download
                                className="flex items-center gap-2 px-4 py-2 bg-gray-900 hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-100 text-white dark:text-gray-900 rounded-lg font-medium transition-all"
                            >
                                <Download className="w-4 h-4" />
                                Download PDF
                            </a>
                        )}
                    </div>
                </div>

                {/* Slide Viewer */}
                <div className="flex-1 flex flex-col items-center justify-center p-6 bg-gray-100 dark:bg-gray-800/50">
                    {/* Current Slide */}
                    <div className="relative w-full max-w-4xl aspect-[16/9] bg-white dark:bg-gray-900 rounded-xl shadow-xl overflow-hidden">
                        {currentSlide?.image_url ? (
                            <img
                                src={currentSlide.image_url}
                                alt={currentSlide.title || `Slide ${currentIndex + 1}`}
                                className="w-full h-full object-contain"
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-gray-400">
                                No image available
                            </div>
                        )}
                    </div>

                    {/* Navigation */}
                    <div className="flex items-center gap-4 mt-6">
                        <button
                            onClick={goToPrevious}
                            disabled={currentIndex === 0}
                            className="p-2 hover:bg-white dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-30"
                        >
                            <ChevronLeft className="w-6 h-6 text-gray-600 dark:text-gray-400" />
                        </button>

                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                            {currentIndex + 1} / {totalSlides}
                        </span>

                        <button
                            onClick={goToNext}
                            disabled={currentIndex === totalSlides - 1}
                            className="p-2 hover:bg-white dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-30"
                        >
                            <ChevronRight className="w-6 h-6 text-gray-600 dark:text-gray-400" />
                        </button>
                    </div>

                    {/* Thumbnail Strip */}
                    <div className="flex gap-2 mt-4 overflow-x-auto max-w-full pb-2">
                        {slides.map((slide, index) => (
                            <button
                                key={index}
                                onClick={() => goToSlide(index)}
                                className={`flex-shrink-0 w-20 h-14 rounded-lg overflow-hidden border-2 transition-all ${
                                    index === currentIndex
                                        ? "border-blue-500 ring-2 ring-blue-200 dark:ring-blue-800"
                                        : "border-transparent hover:border-gray-300 dark:hover:border-gray-600"
                                }`}
                            >
                                {slide.image_url ? (
                                    <img
                                        src={slide.image_url}
                                        alt={`Slide ${index + 1}`}
                                        className="w-full h-full object-cover"
                                    />
                                ) : (
                                    <div className="w-full h-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-xs text-gray-500">
                                        {index + 1}
                                    </div>
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Edit Panel (Right Side) */}
            <div className="w-80 flex-shrink-0 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 flex flex-col">
                <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                        Edit Slide {currentIndex + 1}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {currentSlide?.title || "Untitled"}
                    </p>
                </div>

                <div className="flex-1 p-4 space-y-4 overflow-y-auto">
                    {/* Prompt Input */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                            Regeneration Prompt
                        </label>
                        <textarea
                            value={editPrompt}
                            onChange={(e) => setEditPrompt(e.target.value)}
                            placeholder="Describe how you want to modify this slide..."
                            rows={4}
                            className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>

                    {/* Reference Image Upload */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                            Reference Image (Optional)
                        </label>

                        {referencePreview ? (
                            <div className="relative">
                                <img
                                    src={referencePreview}
                                    alt="Reference"
                                    className="w-full aspect-video object-cover rounded-lg border border-gray-200 dark:border-gray-700"
                                />
                                <button
                                    onClick={clearReferenceImage}
                                    className="absolute top-2 right-2 p-1 bg-red-500 hover:bg-red-600 text-white rounded-full"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            </div>
                        ) : (
                            <div
                                onClick={() => fileInputRef.current?.click()}
                                className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center cursor-pointer hover:border-gray-400 dark:hover:border-gray-500 transition-colors"
                            >
                                <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    Click to upload
                                </p>
                            </div>
                        )}

                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            onChange={handleImageUpload}
                            className="hidden"
                        />
                    </div>

                    {/* Error Message */}
                    {(error || regenerateError) && (
                        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                            <p className="text-sm text-red-600 dark:text-red-400">
                                {error || regenerateError}
                            </p>
                        </div>
                    )}
                </div>

                {/* Regenerate Button */}
                <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                    <button
                        onClick={handleRegenerate}
                        disabled={isRegenerating || (!editPrompt.trim() && !referenceImage)}
                        className="w-full flex items-center justify-center gap-2 py-2.5 bg-gray-900 hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-100 text-white dark:text-gray-900 rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isRegenerating ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Regenerating...
                            </>
                        ) : (
                            <>
                                <RefreshCw className="w-4 h-4" />
                                Regenerate Slide
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SlideEditorStep;
