import React, { useState, useEffect, useCallback, useRef } from "react";
import UploadStep from "./UploadStep";
import ProcessingStep from "./ProcessingStep";
import OutlineEditorStep from "./OutlineEditorStep";
import GeneratingStep from "./GeneratingStep";
import SlideEditorStep from "./SlideEditorStep";

// Wizard steps
const STEPS = {
    UPLOAD: "upload",
    PROCESSING: "processing",
    OUTLINE: "outline",
    GENERATING: "generating",
    EDITOR: "editor",
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

        if (!conversation) {
            setCurrentStep(STEPS.UPLOAD);
            setSessionId(null);
            setFiles([]);
            setPlan(null);
            return;
        }

        // Check if there's a session with files
        const sessionFiles = conversation.files || [];
        const savedSessionId = sessionFiles.length > 0 && sessionFiles[0]?.sessionId
            ? sessionFiles[0].sessionId
            : null;

        setSessionId(savedSessionId);
        setFiles(sessionFiles);

        // Check for saved wizard state
        const savedState = conversation.wizardState;

        // Priority 1: Completed outputs - show editor
        if (conversation.generatedOutputs?.length > 0) {
            const latestOutput = conversation.generatedOutputs[conversation.generatedOutputs.length - 1];
            if (latestOutput?.slides) {
                setSlides(latestOutput.slides);
            }
            setPlan(null);
            setCurrentStep(STEPS.EDITOR);
            return;
        }

        // Priority 2: Saved wizard state - restore and potentially resume
        if (savedState?.sessionId && savedSessionId) {
            // Restore plan if available
            if (savedState.plan) {
                setPlan(savedState.plan);
            }

            // Restore to the appropriate step
            if (savedState.step === STEPS.OUTLINE && savedState.plan) {
                // Was editing outline - restore it
                setCurrentStep(STEPS.OUTLINE);
            } else if (savedState.step === STEPS.PROCESSING || savedState.step === STEPS.GENERATING) {
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
        if (sessionId && (currentStep === STEPS.PROCESSING || currentStep === STEPS.OUTLINE || currentStep === STEPS.GENERATING)) {
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

    // Start processing after upload
    const handleStartProcessing = useCallback(async (uploadedFiles, uploadConfig) => {
        setError(null);
        setIsLoading(true);

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
                formData.append("fast_mode", uploadConfig.fastMode ? "true" : "false");
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
                throw new Error(errorData.detail || `HTTP error ${response.status}`);
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
        }
    }, [conversation, onUpdateConversation]);

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
                        generatedOutputs: [{
                            id: Date.now().toString(),
                            slides: resultData.slides,
                            pptUrl: resultData.ppt_url,
                            posterUrl: resultData.poster_url,
                            timestamp: new Date().toISOString(),
                        }],
                    });
                }
            }
        } catch (err) {
            console.error("Error fetching results:", err);
        }
    };

    // Handle plan confirmation
    const handleConfirmPlan = useCallback(async (editedSections) => {
        setError(null);
        setIsLoading(true);

        try {
            // Save edited plan if sections were modified
            if (editedSections) {
                const updateResponse = await fetch(`/api/plan/${sessionId}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ sections: editedSections }),
                });

                if (!updateResponse.ok) {
                    throw new Error("Failed to save plan changes");
                }
            }

            // Confirm plan and start generation
            const confirmResponse = await fetch(`/api/plan/${sessionId}/confirm`, {
                method: "POST",
            });

            if (!confirmResponse.ok) {
                const errorData = await confirmResponse.json().catch(() => ({}));
                throw new Error(errorData.detail || "Failed to confirm plan");
            }

            // Move to generating step and start polling
            setCurrentStep(STEPS.GENERATING);
            startStatusPolling(sessionId);

        } catch (err) {
            setError(err.message);
            setIsLoading(false);
        }
    }, [sessionId, startStatusPolling]);

    // Handle slide regeneration
    const handleRegenerateSlide = useCallback(async (slideIndex, prompt, referenceImage) => {
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

            const response = await fetch(`/api/slides/${sessionId}/regenerate`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || "Failed to regenerate slide");
            }

            const result = await response.json();

            // Update slides array with new image
            setSlides((prev) =>
                prev.map((slide, idx) =>
                    idx === slideIndex
                        ? { ...slide, image_url: result.image_url + `?t=${Date.now()}` }
                        : slide
                )
            );

            return result;
        } catch (err) {
            setError(err.message);
            throw err;
        }
    }, [sessionId]);

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
                    <ProcessingStep
                        stages={stages}
                        onCancel={handleCancel}
                    />
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
                        error={error}
                    />
                );

            default:
                return null;
        }
    };

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            {renderStep()}
        </div>
    );
};

export default WizardContainer;
