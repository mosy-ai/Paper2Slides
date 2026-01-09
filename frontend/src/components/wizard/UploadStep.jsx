import React, { useState, useRef, useCallback } from "react";
import { Upload, FileText, X, ChevronDown, ChevronUp, Zap, Globe } from "lucide-react";

const UploadStep = ({ config, setConfig, onStartProcessing, error }) => {
    const [files, setFiles] = useState([]);
    const [isDragging, setIsDragging] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const fileInputRef = useRef(null);

    const handleDragOver = useCallback((e) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        setIsDragging(false);

        const droppedFiles = Array.from(e.dataTransfer.files).filter(
            (file) =>
                file.type === "application/pdf" ||
                file.name.toLowerCase().endsWith(".pdf")
        );

        if (droppedFiles.length > 0) {
            setFiles((prev) => [...prev, ...droppedFiles]);
        }
    }, []);

    const handleFileSelect = useCallback((e) => {
        const selectedFiles = Array.from(e.target.files).filter(
            (file) =>
                file.type === "application/pdf" ||
                file.name.toLowerCase().endsWith(".pdf")
        );

        if (selectedFiles.length > 0) {
            setFiles((prev) => [...prev, ...selectedFiles]);
        }
    }, []);

    const handleRemoveFile = useCallback((index) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    }, []);

    const handleStartClick = useCallback(() => {
        if (files.length === 0) return;
        onStartProcessing(files, config);
    }, [files, config, onStartProcessing]);

    const formatFileSize = (bytes) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="flex-1 flex flex-col items-center justify-center p-8">
            <div className="w-full max-w-2xl">
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="w-16 h-16 rounded-2xl bg-gray-900 dark:bg-white flex items-center justify-center mx-auto mb-4 shadow-xl">
                        <FileText className="w-8 h-8 text-white dark:text-gray-900" />
                    </div>
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                        Upload Your Document
                    </h2>
                    <p className="text-gray-600 dark:text-gray-400">
                        Upload a PDF file to transform it into a presentation
                    </p>
                </div>

                {/* Upload Area */}
                <div
                    className={`
                        relative border-2 border-dashed rounded-2xl p-8 text-center
                        transition-all cursor-pointer
                        ${isDragging
                            ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                            : "border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600"
                        }
                    `}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                >
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf"
                        multiple
                        className="hidden"
                        onChange={handleFileSelect}
                    />

                    <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                    <p className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Drag and drop your PDF here
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        or click to browse
                    </p>
                </div>

                {/* File List */}
                {files.length > 0 && (
                    <div className="mt-4 space-y-2">
                        {files.map((file, index) => (
                            <div
                                key={index}
                                className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-xl"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-lg bg-gray-900 dark:bg-white flex items-center justify-center">
                                        <FileText className="w-5 h-5 text-white dark:text-gray-900" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[300px]">
                                            {file.name}
                                        </p>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">
                                            {formatFileSize(file.size)}
                                        </p>
                                    </div>
                                </div>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRemoveFile(index);
                                    }}
                                    className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                                >
                                    <X className="w-4 h-4 text-gray-500" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Config Options */}
                <div className="mt-6 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
                    {/* Main Options */}
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        {/* Output Type */}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                                Output Type
                            </label>
                            <select
                                value={config.output}
                                onChange={(e) => setConfig({ ...config, output: e.target.value })}
                                className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm"
                            >
                                <option value="slides">Slides</option>
                                <option value="poster">Poster</option>
                            </select>
                        </div>

                        {/* Style */}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                                Style
                            </label>
                            <select
                                value={config.style}
                                onChange={(e) => setConfig({ ...config, style: e.target.value })}
                                className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm"
                            >
                                <option value="academic">Academic</option>
                            </select>
                        </div>
                    </div>

                    {/* Length/Density */}
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        {config.output === "slides" ? (
                            <div>
                                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                                    Length
                                </label>
                                <select
                                    value={config.length}
                                    onChange={(e) => setConfig({ ...config, length: e.target.value })}
                                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm"
                                >
                                    <option value="short">Short (5-8 slides)</option>
                                    <option value="medium">Medium (8-12 slides)</option>
                                    <option value="long">Long (12-15 slides)</option>
                                </select>
                            </div>
                        ) : (
                            <div>
                                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                                    Density
                                </label>
                                <select
                                    value={config.density}
                                    onChange={(e) => setConfig({ ...config, density: e.target.value })}
                                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm"
                                >
                                    <option value="sparse">Sparse</option>
                                    <option value="medium">Medium</option>
                                    <option value="dense">Dense</option>
                                </select>
                            </div>
                        )}

                        {/* Language */}
                        <div>
                            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                                Language
                            </label>
                            <select
                                value={config.language}
                                onChange={(e) => setConfig({ ...config, language: e.target.value })}
                                className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm"
                            >
                                <option value="vietnamese">Vietnamese</option>
                                <option value="english">English</option>
                            </select>
                        </div>
                    </div>

                    {/* Advanced Options Toggle */}
                    <button
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                    >
                        {showAdvanced ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        Advanced Options
                    </button>

                    {/* Advanced Options */}
                    {showAdvanced && (
                        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 space-y-3">
                            {/* Content Type */}
                            <div>
                                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                                    Content Type
                                </label>
                                <select
                                    value={config.content}
                                    onChange={(e) => setConfig({ ...config, content: e.target.value })}
                                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm"
                                >
                                    <option value="paper">Academic Paper</option>
                                    <option value="general">General Document</option>
                                </select>
                            </div>

                            {/* Fast Mode */}
                            {config.content === "paper" && (
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={config.fastMode}
                                        onChange={(e) => setConfig({ ...config, fastMode: e.target.checked })}
                                        className="w-4 h-4 rounded border-gray-300"
                                    />
                                    <span className="text-sm text-gray-700 dark:text-gray-300 flex items-center gap-1">
                                        <Zap className="w-3.5 h-3.5" />
                                        Fast Mode (skip RAG indexing)
                                    </span>
                                </label>
                            )}
                        </div>
                    )}
                </div>

                {/* Error Message */}
                {error && (
                    <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                    </div>
                )}

                {/* Start Button */}
                <button
                    onClick={handleStartClick}
                    disabled={files.length === 0}
                    className={`
                        w-full mt-6 py-3 rounded-xl font-medium transition-all
                        ${files.length > 0
                            ? "bg-gray-900 hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-100 text-white dark:text-gray-900 shadow-lg hover:shadow-xl"
                            : "bg-gray-200 dark:bg-gray-800 text-gray-400 dark:text-gray-600 cursor-not-allowed"
                        }
                    `}
                >
                    Start Processing
                </button>
            </div>
        </div>
    );
};

export default UploadStep;
