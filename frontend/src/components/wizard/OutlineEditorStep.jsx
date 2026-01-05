import React, { useState, useCallback, useEffect } from "react";
import {
    ArrowRight,
    Edit2,
    Trash2,
    Plus,
    GripVertical,
    ChevronDown,
    ChevronUp,
    Image,
    Table,
    X,
    Check,
    FileText,
} from "lucide-react";

const SECTION_TYPES = [
    { value: "opening", label: "Opening" },
    { value: "content", label: "Content" },
    { value: "ending", label: "Ending" },
];

const OutlineEditorStep = ({ plan, onConfirm, onPlanChange, isLoading, error }) => {
    const [sections, setSections] = useState(plan?.plan?.sections || []);
    const [editingId, setEditingId] = useState(null);
    const [expandedId, setExpandedId] = useState(null);
    const [editForm, setEditForm] = useState({});

    // Auto-save sections when they change
    useEffect(() => {
        if (onPlanChange && sections.length > 0) {
            onPlanChange(sections);
        }
    }, [sections, onPlanChange]);

    // Get available figures and tables
    const figures = Object.entries(plan?.figures_index || {}).map(([id, info]) => ({
        id,
        caption: info.caption,
    }));
    const tables = Object.entries(plan?.tables_index || {}).map(([id, info]) => ({
        id,
        caption: info.caption,
    }));

    // Handle section reorder
    const moveSection = useCallback((index, direction) => {
        const newSections = [...sections];
        const targetIndex = direction === "up" ? index - 1 : index + 1;

        if (targetIndex < 0 || targetIndex >= sections.length) return;

        [newSections[index], newSections[targetIndex]] = [
            newSections[targetIndex],
            newSections[index],
        ];

        // Update IDs to maintain order
        newSections.forEach((section, i) => {
            section.id = `section_${i + 1}`;
        });

        setSections(newSections);
    }, [sections]);

    // Handle edit section
    const startEdit = useCallback((section) => {
        setEditingId(section.id);
        setEditForm({
            title: section.title,
            content: section.content,
            type: section.type || "content",
            figures: section.figures?.map((f) => f.figure_id) || [],
            tables: section.tables?.map((t) => t.table_id) || [],
        });
    }, []);

    const saveEdit = useCallback(() => {
        setSections((prev) =>
            prev.map((section) => {
                if (section.id === editingId) {
                    return {
                        ...section,
                        title: editForm.title,
                        content: editForm.content,
                        type: editForm.type,
                        figures: editForm.figures.map((id) => ({ figure_id: id })),
                        tables: editForm.tables.map((id) => ({ table_id: id })),
                    };
                }
                return section;
            })
        );
        setEditingId(null);
        setEditForm({});
    }, [editingId, editForm]);

    const cancelEdit = useCallback(() => {
        setEditingId(null);
        setEditForm({});
    }, []);

    // Handle delete section
    const deleteSection = useCallback((id) => {
        setSections((prev) => {
            const newSections = prev.filter((s) => s.id !== id);
            // Re-number sections
            newSections.forEach((section, i) => {
                section.id = `section_${i + 1}`;
            });
            return newSections;
        });
    }, []);

    // Handle add section
    const addSection = useCallback(() => {
        const newSection = {
            id: `section_${sections.length + 1}`,
            title: "New Slide",
            content: "",
            type: "content",
            figures: [],
            tables: [],
        };
        setSections((prev) => [...prev, newSection]);
        startEdit(newSection);
    }, [sections.length, startEdit]);

    // Handle confirm
    const handleConfirm = useCallback(() => {
        onConfirm(sections);
    }, [sections, onConfirm]);

    // Toggle figure/table in edit form
    const toggleFigure = useCallback((figureId) => {
        setEditForm((prev) => ({
            ...prev,
            figures: prev.figures.includes(figureId)
                ? prev.figures.filter((id) => id !== figureId)
                : [...prev.figures, figureId],
        }));
    }, []);

    const toggleTable = useCallback((tableId) => {
        setEditForm((prev) => ({
            ...prev,
            tables: prev.tables.includes(tableId)
                ? prev.tables.filter((id) => id !== tableId)
                : [...prev.tables, tableId],
        }));
    }, []);

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
                        <FileText className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                            Review & Edit Outline
                        </h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {sections.length} slides
                        </p>
                    </div>
                </div>

                <button
                    onClick={handleConfirm}
                    disabled={isLoading || sections.length === 0}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-900 hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-100 text-white dark:text-gray-900 rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isLoading ? "Processing..." : "Generate Slides"}
                    <ArrowRight className="w-4 h-4" />
                </button>
            </div>

            {/* Error */}
            {error && (
                <div className="mx-6 mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                    <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                </div>
            )}

            {/* Section List */}
            <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-3xl mx-auto space-y-3">
                    {sections.map((section, index) => (
                        <div
                            key={section.id}
                            className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden"
                        >
                            {/* Section Header */}
                            <div className="flex items-center gap-3 p-4">
                                {/* Drag Handle & Index */}
                                <div className="flex items-center gap-2 text-gray-400">
                                    <GripVertical className="w-4 h-4 cursor-grab" />
                                    <span className="text-sm font-medium w-6">
                                        {index + 1}
                                    </span>
                                </div>

                                {/* Title & Type */}
                                <div className="flex-1 min-w-0">
                                    {editingId === section.id ? (
                                        <input
                                            type="text"
                                            value={editForm.title}
                                            onChange={(e) =>
                                                setEditForm((prev) => ({
                                                    ...prev,
                                                    title: e.target.value,
                                                }))
                                            }
                                            className="w-full px-2 py-1 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm"
                                            autoFocus
                                        />
                                    ) : (
                                        <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate">
                                            {section.title}
                                        </h3>
                                    )}
                                    <div className="flex items-center gap-2 mt-1">
                                        <span
                                            className={`text-xs px-2 py-0.5 rounded-full ${
                                                section.type === "opening"
                                                    ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                                                    : section.type === "ending"
                                                    ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300"
                                                    : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
                                            }`}
                                        >
                                            {section.type || "content"}
                                        </span>
                                        {section.figures?.length > 0 && (
                                            <span className="flex items-center gap-0.5 text-xs text-gray-500">
                                                <Image className="w-3 h-3" />
                                                {section.figures.length}
                                            </span>
                                        )}
                                        {section.tables?.length > 0 && (
                                            <span className="flex items-center gap-0.5 text-xs text-gray-500">
                                                <Table className="w-3 h-3" />
                                                {section.tables.length}
                                            </span>
                                        )}
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex items-center gap-1">
                                    {editingId === section.id ? (
                                        <>
                                            <button
                                                onClick={saveEdit}
                                                className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-lg"
                                            >
                                                <Check className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={cancelEdit}
                                                className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                                            >
                                                <X className="w-4 h-4" />
                                            </button>
                                        </>
                                    ) : (
                                        <>
                                            <button
                                                onClick={() =>
                                                    setExpandedId(
                                                        expandedId === section.id ? null : section.id
                                                    )
                                                }
                                                className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                                            >
                                                {expandedId === section.id ? (
                                                    <ChevronUp className="w-4 h-4" />
                                                ) : (
                                                    <ChevronDown className="w-4 h-4" />
                                                )}
                                            </button>
                                            <button
                                                onClick={() => moveSection(index, "up")}
                                                disabled={index === 0}
                                                className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg disabled:opacity-30"
                                            >
                                                <ChevronUp className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={() => moveSection(index, "down")}
                                                disabled={index === sections.length - 1}
                                                className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg disabled:opacity-30"
                                            >
                                                <ChevronDown className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={() => startEdit(section)}
                                                className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={() => deleteSection(section.id)}
                                                className="p-1.5 text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </>
                                    )}
                                </div>
                            </div>

                            {/* Expanded Content */}
                            {(expandedId === section.id || editingId === section.id) && (
                                <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
                                    <div className="pt-3 space-y-3">
                                        {/* Content */}
                                        <div>
                                            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                                                Content
                                            </label>
                                            {editingId === section.id ? (
                                                <textarea
                                                    value={editForm.content}
                                                    onChange={(e) =>
                                                        setEditForm((prev) => ({
                                                            ...prev,
                                                            content: e.target.value,
                                                        }))
                                                    }
                                                    rows={4}
                                                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm resize-none"
                                                />
                                            ) : (
                                                <p className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
                                                    {section.content || "No content"}
                                                </p>
                                            )}
                                        </div>

                                        {/* Type selector (edit mode) */}
                                        {editingId === section.id && (
                                            <div>
                                                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                                                    Section Type
                                                </label>
                                                <select
                                                    value={editForm.type}
                                                    onChange={(e) =>
                                                        setEditForm((prev) => ({
                                                            ...prev,
                                                            type: e.target.value,
                                                        }))
                                                    }
                                                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm"
                                                >
                                                    {SECTION_TYPES.map((type) => (
                                                        <option key={type.value} value={type.value}>
                                                            {type.label}
                                                        </option>
                                                    ))}
                                                </select>
                                            </div>
                                        )}

                                        {/* Figures & Tables (edit mode) */}
                                        {editingId === section.id && (
                                            <div className="grid grid-cols-2 gap-3">
                                                {/* Figures */}
                                                {figures.length > 0 && (
                                                    <div>
                                                        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                                                            Figures
                                                        </label>
                                                        <div className="space-y-1">
                                                            {figures.map((fig) => (
                                                                <label
                                                                    key={fig.id}
                                                                    className="flex items-center gap-2 cursor-pointer"
                                                                >
                                                                    <input
                                                                        type="checkbox"
                                                                        checked={editForm.figures.includes(fig.id)}
                                                                        onChange={() => toggleFigure(fig.id)}
                                                                        className="w-3.5 h-3.5 rounded"
                                                                    />
                                                                    <span className="text-xs text-gray-600 dark:text-gray-400 truncate">
                                                                        {fig.id}
                                                                    </span>
                                                                </label>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Tables */}
                                                {tables.length > 0 && (
                                                    <div>
                                                        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                                                            Tables
                                                        </label>
                                                        <div className="space-y-1">
                                                            {tables.map((tbl) => (
                                                                <label
                                                                    key={tbl.id}
                                                                    className="flex items-center gap-2 cursor-pointer"
                                                                >
                                                                    <input
                                                                        type="checkbox"
                                                                        checked={editForm.tables.includes(tbl.id)}
                                                                        onChange={() => toggleTable(tbl.id)}
                                                                        className="w-3.5 h-3.5 rounded"
                                                                    />
                                                                    <span className="text-xs text-gray-600 dark:text-gray-400 truncate">
                                                                        {tbl.id}
                                                                    </span>
                                                                </label>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {/* Referenced assets (view mode) */}
                                        {editingId !== section.id && (
                                            <div className="flex flex-wrap gap-2">
                                                {section.figures?.map((fig) => (
                                                    <span
                                                        key={fig.figure_id}
                                                        className="flex items-center gap-1 text-xs px-2 py-1 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 rounded"
                                                    >
                                                        <Image className="w-3 h-3" />
                                                        {fig.figure_id}
                                                    </span>
                                                ))}
                                                {section.tables?.map((tbl) => (
                                                    <span
                                                        key={tbl.table_id}
                                                        className="flex items-center gap-1 text-xs px-2 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded"
                                                    >
                                                        <Table className="w-3 h-3" />
                                                        {tbl.table_id}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Add Section Button */}
                    <button
                        onClick={addSection}
                        className="w-full py-3 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl text-gray-500 dark:text-gray-400 hover:border-gray-400 dark:hover:border-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors flex items-center justify-center gap-2"
                    >
                        <Plus className="w-4 h-4" />
                        Add Slide
                    </button>
                </div>
            </div>
        </div>
    );
};

export default OutlineEditorStep;
