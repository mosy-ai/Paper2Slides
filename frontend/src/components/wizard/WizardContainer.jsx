import React, { useState, useEffect, useCallback, useRef } from "react";
import { Loader2 } from "lucide-react";
import UploadStep from "./UploadStep";
import ProcessingStep from "./ProcessingStep";
import OutlineEditorStep from "./OutlineEditorStep";
import GeneratingStep from "./GeneratingStep";
import SlideEditorStep from "./SlideEditorStep";
import VideoConfigStep from "./VideoConfigStep";
import VideoGeneratingStep from "./VideoGeneratingStep";

// Wizard steps
const STEPS = {
    UPLOAD: "upload",
    PROCESSING: "processing",
    OUTLINE: "outline",
    GENERATING: "generating",
    EDITOR: "editor",
    // Video generation steps
    VIDEO_CONFIG: "video_config",
    VIDEO_GENERATING: "video_generating",
};

const WizardContainer = ({
    conversation,
    onUpdateConversation,
    config,
    setConfig,
}) => {
    const [currentStep, setCurrentStep] = useState(STEPS.UPLOAD);
    const [sessionId, setSessionId] = useState(null);
    const [files, setFiles] = useState([]);
    const [stages, setStages] = useState({});
    const [plan, setPlan] = useState(null);
    const [slides, setSlides] = useState([]);
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [showInfoModal, setShowInfoModal] = useState(false);

    // Video generation state
    const [videoUrl, setVideoUrl] = useState(null);

    // Helper to check if video exists for a session
    const checkExistingVideo = async (sid) => {
        try {
            const response = await fetch(`/api/video/${sid}/status`);
            if (response.ok) {
                const data = await response.json();
                if (data.status === "completed" && data.output?.video_url) {
                    setVideoUrl(data.output.video_url);
                    return true;
                }
            }
        } catch (err) {
            console.error("Error checking video status:", err);
        }
        return false;
    };

    const pollIntervalRef = useRef(null);
    const abortControllerRef = useRef(null);

    // Determine step based on conversation state (with session persistence)
    useEffect(() => {
        // Clear polling when conversation changes
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
        }

        // Reset state
        setSlides([]);
        setStages({});
        setError(null);
        setIsLoading(false);
        setVideoUrl(null);

        if (!conversation) {
            setCurrentStep(STEPS.UPLOAD);
            setSessionId(null);
            setFiles([]);
            setPlan(null);
            return;
        }

        // Check if there's a session with files
        const sessionFiles = conversation.files || [];
        const savedSessionId =
            sessionFiles.length > 0 && sessionFiles[0]?.sessionId
                ? sessionFiles[0].sessionId
                : null;

        setSessionId(savedSessionId);
        setFiles(sessionFiles);

        // Get cached data for fallback
        const latestOutput =
            conversation.generatedOutputs?.[
                conversation.generatedOutputs.length - 1
            ];
        const cachedSlides = latestOutput?.slides || [];

        // Priority 1: Check for active session via status API
        if (savedSessionId) {
            (async () => {
                try {
                    const statusResponse = await fetch(
                        `/api/status/${savedSessionId}`,
                    );
                    if (!statusResponse.ok) {
                        // Session doesn't exist or error - fall back to cached data or upload
                        if (cachedSlides.length > 0) {
                            setSlides(cachedSlides);
                            setPlan(null);
                            setCurrentStep(STEPS.EDITOR);
                            // Check if video already exists
                            await checkExistingVideo(savedSessionId);
                        } else {
                            setCurrentStep(STEPS.UPLOAD);
                        }
                        return;
                    }

                    const statusData = await statusResponse.json();
                    const status = statusData.status;

                    if (status === "completed") {
                        // Fetch results and show editor
                        const resultResponse = await fetch(
                            `/api/result/${savedSessionId}`,
                        );
                        if (resultResponse.ok) {
                            const resultData = await resultResponse.json();
                            if (resultData.slides?.length > 0) {
                                setSlides(resultData.slides);
                                setPlan(null);
                                setCurrentStep(STEPS.EDITOR);

                                // Check if video already exists
                                await checkExistingVideo(savedSessionId);

                                // Update stored data
                                if (onUpdateConversation) {
                                    onUpdateConversation(conversation.id, {
                                        generatedOutputs: [
                                            {
                                                id: Date.now().toString(),
                                                slides: resultData.slides,
                                                pptUrl: resultData.ppt_url,
                                                posterUrl:
                                                    resultData.poster_url,
                                                timestamp:
                                                    new Date().toISOString(),
                                            },
                                        ],
                                    });
                                }
                                return;
                            }
                        }
                        // Fall back to cached
                        if (cachedSlides.length > 0) {
                            setSlides(cachedSlides);
                            setPlan(null);
                            setCurrentStep(STEPS.EDITOR);
                            // Check if video already exists
                            await checkExistingVideo(savedSessionId);
                        }
                    } else if (status === "awaiting_confirmation") {
                        // Restore to OUTLINE step and fetch plan
                        const planResponse = await fetch(
                            `/api/plan/${savedSessionId}`,
                        );
                        if (planResponse.ok) {
                            const planData = await planResponse.json();
                            setPlan(planData);
                        }
                        setCurrentStep(STEPS.OUTLINE);
                    } else if (status === "running") {
                        // Determine which step based on stages
                        const stages = statusData.stages || {};
                        if (
                            stages.generate === "running" ||
                            stages.generate === "completed"
                        ) {
                            setCurrentStep(STEPS.GENERATING);
                        } else {
                            setCurrentStep(STEPS.PROCESSING);
                        }
                        // Resume polling
                        setStages(stages);
                        setIsLoading(true);
                        setTimeout(() => {
                            startStatusPolling(savedSessionId);
                        }, 100);
                    } else if (status === "failed") {
                        setError(statusData.error || "Processing failed");
                        setCurrentStep(STEPS.UPLOAD);
                    } else {
                        // Unknown status - default to upload
                        setCurrentStep(STEPS.UPLOAD);
                    }
                } catch (err) {
                    console.error("Error restoring session:", err);
                    // Fall back to cached data or upload
                    if (cachedSlides.length > 0) {
                        setSlides(cachedSlides);
                        setPlan(null);
                        setCurrentStep(STEPS.EDITOR);
                        // Check if video already exists
                        await checkExistingVideo(savedSessionId);
                    } else {
                        setCurrentStep(STEPS.UPLOAD);
                    }
                }
            })();
            return;
        }

        // Priority 2: Cached slides without session
        if (cachedSlides.length > 0) {
            setSlides(cachedSlides);
            setPlan(null);
            setCurrentStep(STEPS.EDITOR);
            // Note: Can't check video without sessionId
            return;
        }

        // Priority 3: Saved wizard state (deprecated but kept for backward compatibility)
        const savedState = conversation.wizardState;
        if (savedState?.sessionId && savedSessionId) {
            // Restore plan if available
            if (savedState.plan) {
                setPlan(savedState.plan);
            }

            // Restore to the appropriate step
            if (savedState.step === STEPS.OUTLINE && savedState.plan) {
                // Was editing outline - restore it
                setCurrentStep(STEPS.OUTLINE);
            } else if (
                savedState.step === STEPS.PROCESSING ||
                savedState.step === STEPS.GENERATING
            ) {
                // Was in progress - resume polling
                setCurrentStep(savedState.step);
                setIsLoading(true);
                // Start polling after a small delay to let state settle
                setTimeout(() => {
                    startStatusPolling(savedSessionId);
                }, 100);
            } else {
                // Default to upload for unknown states
                setPlan(null);
                setCurrentStep(STEPS.UPLOAD);
            }
            return;
        }

        // Priority 3: New or empty conversation
        setPlan(null);
        setCurrentStep(STEPS.UPLOAD);
    }, [conversation?.id]);

    // Save wizard state to conversation when it changes
    useEffect(() => {
        if (!conversation || !onUpdateConversation) return;

        // Only save if we have a session and are in a saveable state
        if (
            sessionId &&
            (currentStep === STEPS.PROCESSING ||
                currentStep === STEPS.OUTLINE ||
                currentStep === STEPS.GENERATING)
        ) {
            const wizardState = {
                step: currentStep,
                sessionId: sessionId,
                plan: plan,
                savedAt: new Date().toISOString(),
            };

            // Debounce the save to avoid too many updates
            const timeoutId = setTimeout(() => {
                onUpdateConversation(conversation.id, { wizardState });
            }, 500);

            return () => clearTimeout(timeoutId);
        }
    }, [currentStep, sessionId, plan, conversation?.id, onUpdateConversation]);

    // Clean up polling on unmount
    useEffect(() => {
        return () => {
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
            }
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    // Auto-dismiss info modal when step changes
    useEffect(() => {
        if (currentStep !== STEPS.UPLOAD && showInfoModal) {
            setShowInfoModal(false);
        }
    }, [currentStep, showInfoModal]);

    // Start processing after upload
    const handleStartProcessing = useCallback(
        async (uploadedFiles, uploadConfig) => {
            setError(null);
            setIsLoading(true);
            setShowInfoModal(true);

            try {
                abortControllerRef.current = new AbortController();

                const formData = new FormData();
                formData.append("message", "");
                formData.append("content", uploadConfig.content);
                formData.append("output_type", uploadConfig.output);
                formData.append("style", uploadConfig.style);
                formData.append("language", uploadConfig.language);

                if (uploadConfig.output === "slides") {
                    formData.append("length", uploadConfig.length);
                } else {
                    formData.append("density", uploadConfig.density);
                }

                if (uploadConfig.content === "paper") {
                    formData.append(
                        "fast_mode",
                        uploadConfig.fastMode ? "true" : "false",
                    );
                }

                uploadedFiles.forEach((file) => {
                    formData.append("files", file);
                });

                const response = await fetch("/api/chat", {
                    method: "POST",
                    body: formData,
                    signal: abortControllerRef.current.signal,
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(
                        errorData.detail || `HTTP error ${response.status}`,
                    );
                }

                const data = await response.json();
                setSessionId(data.session_id);

                // Update conversation with files and session
                if (onUpdateConversation && conversation) {
                    const fileInfos = data.uploaded_files.map((f) => ({
                        name: f.name,
                        size: f.size,
                        url: f.url,
                        sessionId: data.session_id,
                    }));
                    onUpdateConversation(conversation.id, {
                        files: fileInfos,
                        config: uploadConfig,
                    });
                }

                // Move to processing step and start polling
                setCurrentStep(STEPS.PROCESSING);
                startStatusPolling(data.session_id);
            } catch (err) {
                if (err.name === "AbortError") {
                    setError("Upload cancelled");
                } else {
                    setError(err.message);
                }
                setIsLoading(false);
                setShowInfoModal(false);
            }
        },
        [conversation, onUpdateConversation],
    );

    // Poll for status updates
    const startStatusPolling = useCallback((sid) => {
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
        }

        const poll = async () => {
            try {
                const response = await fetch(`/api/status/${sid}`);
                if (!response.ok) return;

                const statusData = await response.json();
                setStages(statusData.stages || {});

                // Check status and transition steps
                if (statusData.status === "awaiting_confirmation") {
                    // Plan is ready, fetch it and move to outline step
                    clearInterval(pollIntervalRef.current);
                    await fetchPlan(sid);
                    setCurrentStep(STEPS.OUTLINE);
                    setIsLoading(false);
                } else if (statusData.status === "completed") {
                    // All done, fetch results and move to editor
                    clearInterval(pollIntervalRef.current);
                    await fetchResults(sid);
                    setCurrentStep(STEPS.EDITOR);
                    setIsLoading(false);
                } else if (statusData.status === "failed") {
                    clearInterval(pollIntervalRef.current);
                    setError(statusData.error || "Processing failed");
                    setIsLoading(false);
                }
            } catch (err) {
                console.error("Error polling status:", err);
            }
        };

        // Poll immediately and then every 1.5 seconds
        poll();
        pollIntervalRef.current = setInterval(poll, 1500);
    }, []);

    // Fetch plan data
    const fetchPlan = async (sid) => {
        try {
            const response = await fetch(`/api/plan/${sid}`);
            if (response.ok) {
                const planData = await response.json();
                setPlan(planData);
            }
        } catch (err) {
            console.error("Error fetching plan:", err);
        }
    };

    // Fetch final results
    const fetchResults = async (sid) => {
        try {
            const response = await fetch(`/api/result/${sid}`);
            if (response.ok) {
                const resultData = await response.json();
                setSlides(resultData.slides || []);

                // Update conversation with results
                if (onUpdateConversation && conversation) {
                    onUpdateConversation(conversation.id, {
                        generatedOutputs: [
                            {
                                id: Date.now().toString(),
                                slides: resultData.slides,
                                pptUrl: resultData.ppt_url,
                                posterUrl: resultData.poster_url,
                                timestamp: new Date().toISOString(),
                            },
                        ],
                    });
                }
            }
        } catch (err) {
            console.error("Error fetching results:", err);
        }
    };

    // Handle plan confirmation
    const handleConfirmPlan = useCallback(
        async (editedSections) => {
            setError(null);
            setIsLoading(true);

            try {
                // Save edited plan if sections were modified
                if (editedSections) {
                    const updateResponse = await fetch(
                        `/api/plan/${sessionId}`,
                        {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ sections: editedSections }),
                        },
                    );

                    if (!updateResponse.ok) {
                        throw new Error("Failed to save plan changes");
                    }
                }

                // Confirm plan and start generation
                const confirmResponse = await fetch(
                    `/api/plan/${sessionId}/confirm`,
                    {
                        method: "POST",
                    },
                );

                if (!confirmResponse.ok) {
                    const errorData = await confirmResponse
                        .json()
                        .catch(() => ({}));
                    throw new Error(
                        errorData.detail || "Failed to confirm plan",
                    );
                }

                // Move to generating step and start polling
                setCurrentStep(STEPS.GENERATING);
                startStatusPolling(sessionId);
            } catch (err) {
                setError(err.message);
                setIsLoading(false);
            }
        },
        [sessionId, startStatusPolling],
    );

    // Handle slide regeneration
    const handleRegenerateSlide = useCallback(
        async (slideIndex, prompt, referenceImage) => {
            setError(null);

            try {
                const formData = new FormData();
                formData.append("slide_index", slideIndex);
                if (prompt) {
                    formData.append("prompt", prompt);
                }
                if (referenceImage) {
                    formData.append("reference_image", referenceImage);
                }

                const response = await fetch(
                    `/api/slides/${sessionId}/regenerate`,
                    {
                        method: "POST",
                        body: formData,
                    },
                );

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(
                        errorData.detail || "Failed to regenerate slide",
                    );
                }

                const result = await response.json();

                // Update slides array with new image
                setSlides((prev) =>
                    prev.map((slide, idx) =>
                        idx === slideIndex
                            ? {
                                  ...slide,
                                  image_url:
                                      result.image_url + `?t=${Date.now()}`,
                              }
                            : slide,
                    ),
                );

                return result;
            } catch (err) {
                setError(err.message);
                throw err;
            }
        },
        [sessionId],
    );

    // Handle cancel
    const handleCancel = useCallback(async () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
        }
        if (sessionId) {
            try {
                await fetch(`/api/cancel/${sessionId}`, { method: "POST" });
            } catch (err) {
                console.error("Error cancelling:", err);
            }
        }
        setIsLoading(false);
        setCurrentStep(STEPS.UPLOAD);
    }, [sessionId]);

    // Handle plan changes from outline editor (auto-save)
    const handlePlanChange = useCallback((editedSections) => {
        setPlan((prev) => ({
            ...prev,
            plan: {
                ...prev?.plan,
                sections: editedSections,
            },
        }));
    }, []);

    // Handle navigating to video generation
    const handleGenerateVideo = useCallback(() => {
        setVideoUrl(null);
        setCurrentStep(STEPS.VIDEO_CONFIG);
    }, []);

    // Handle starting video generation
    const handleStartVideoGeneration = useCallback(
        async (videoConfig) => {
            setError(null);

            // Immediately transition to generating step for better UX
            setCurrentStep(STEPS.VIDEO_GENERATING);

            try {
                const response = await fetch(`/api/video/${sessionId}/generate`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(videoConfig),
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || "Failed to start video generation");
                }

                // Video generation started successfully - VideoGeneratingStep will poll for status
            } catch (err) {
                setError(err.message);
                // Go back to config step on error
                setCurrentStep(STEPS.VIDEO_CONFIG);
                throw err;
            }
        },
        [sessionId]
    );

    // Handle video generation complete - go back to editor with download button
    const handleVideoComplete = useCallback((result) => {
        setVideoUrl(result.video_url);
        setCurrentStep(STEPS.EDITOR);
    }, []);

    // Handle video generation cancel or back
    const handleVideoCancel = useCallback(() => {
        setCurrentStep(STEPS.EDITOR);
    }, []);

    // Render current step
    const renderStep = () => {
        switch (currentStep) {
            case STEPS.UPLOAD:
                return (
                    <UploadStep
                        config={config}
                        setConfig={setConfig}
                        onStartProcessing={handleStartProcessing}
                        error={error}
                    />
                );

            case STEPS.PROCESSING:
                return (
                    <ProcessingStep stages={stages} onCancel={handleCancel} />
                );

            case STEPS.OUTLINE:
                return (
                    <OutlineEditorStep
                        plan={plan}
                        onConfirm={handleConfirmPlan}
                        onPlanChange={handlePlanChange}
                        isLoading={isLoading}
                        error={error}
                    />
                );

            case STEPS.GENERATING:
                return (
                    <GeneratingStep
                        stages={stages}
                        slides={slides}
                        onCancel={handleCancel}
                    />
                );

            case STEPS.EDITOR:
                return (
                    <SlideEditorStep
                        slides={slides}
                        sessionId={sessionId}
                        onRegenerateSlide={handleRegenerateSlide}
                        onGenerateVideo={videoUrl ? null : handleGenerateVideo}
                        videoUrl={videoUrl}
                        error={error}
                    />
                );

            case STEPS.VIDEO_CONFIG:
                return (
                    <VideoConfigStep
                        slides={slides}
                        sessionId={sessionId}
                        onGenerate={handleStartVideoGeneration}
                        onBack={handleVideoCancel}
                    />
                );

            case STEPS.VIDEO_GENERATING:
                return (
                    <VideoGeneratingStep
                        sessionId={sessionId}
                        onComplete={handleVideoComplete}
                        onCancel={handleVideoCancel}
                    />
                );

            default:
                return null;
        }
    };

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            {renderStep()}

            {/* Informational Loading Modal */}
            {showInfoModal && (
                <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
                    <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-6 max-w-md mx-4">
                        {/* Icon */}
                        <div className="flex items-center justify-center w-16 h-16 mx-auto mb-4 bg-blue-100 dark:bg-blue-900/30 rounded-full">
                            <Loader2 className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
                        </div>

                        {/* Title */}
                        <h3 className="text-xl font-semibold text-center text-gray-900 dark:text-gray-100 mb-2">
                            Processing Your Document
                        </h3>

                        {/* Message */}
                        <p className="text-center text-gray-600 dark:text-gray-400 mb-6">
                            We're analyzing your document
                        </p>

                        {/* Progress indicator */}
                        <div className="flex items-center justify-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                            <div className="flex gap-1">
                                <div
                                    className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"
                                    style={{ animationDelay: "0ms" }}
                                ></div>
                                <div
                                    className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"
                                    style={{ animationDelay: "150ms" }}
                                ></div>
                                <div
                                    className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"
                                    style={{ animationDelay: "300ms" }}
                                ></div>
                            </div>
                            <span>Starting...</span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default WizardContainer;
