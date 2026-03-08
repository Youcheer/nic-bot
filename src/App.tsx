/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useRef, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { GoogleGenAI, Type } from "@google/genai";
import {
  Upload,
  FileText,
  Download,
  Copy,
  Check,
  RefreshCw,
  Image as ImageIcon,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// --- Utility ---
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- Types ---
type DocumentType = 'ID' | 'GOP' | 'PASSPORT';

interface DocumentDetails {
  type: DocumentType;
  name: string;
  idNumber?: string; // NIC or Passport Number
  gopNumber?: string;
  expiryDate: string;
  dob: string;
  country?: string; // For GOP/Passport
  rotation?: number; // angle in degrees
  boundingBox?: {
    ymin: number;
    xmin: number;
    ymax: number;
    xmax: number;
  };
}

// --- App Component ---
export default function App() {
  const [images, setImages] = useState<string[]>([]);
  const [croppedImage, setCroppedImage] = useState<string | null>(null);
  const [details, setDetails] = useState<DocumentDetails | null>(null);
  const [accountNumber, setAccountNumber] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const newImages: string[] = [];
      let processedCount = 0;

      acceptedFiles.forEach((file) => {
        const reader = new FileReader();
        reader.onload = () => {
          newImages.push(reader.result as string);
          processedCount++;
          if (processedCount === acceptedFiles.length) {
            setImages(prev => [...prev, ...newImages].slice(0, 2)); // Limit to 2 images
            setCroppedImage(null);
            setDetails(null);
            setError(null);
          }
        };
        reader.readAsDataURL(file);
      });
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [] },
    multiple: true
  } as any);

  const processImages = async () => {
    if (images.length === 0) return;
    setIsProcessing(true);
    setError(null);

    try {
      const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY! });

      const prompt = `
        Analyze the provided image(s). They could be a National ID Card, a Gainful Occupation Permit (GOP), or a Passport.
        
        If it's a National ID (NIC):
        - Extract Name, NIC Number, DOB, and Expiry Date.
        - Provide bounding box and rotation for the ID card.
        
        If it's a GOP (Gainful Occupation Permit):
        - Extract Name, GOP Number (Serial Number), DOB, Country of Birth/Origin, and Expiry Date.
        - If a Passport is also provided, extract the Passport Number (PP Number). If not, set PP Number to "Unknown".
        - Provide bounding box and rotation for the GOP document.
        
        General Rules:
        - Format all dates as DD.MM.YYYY.
        - Rotation angle should straighten the primary document (ID or GOP).
        - Return the data in JSON format.
      `;

      const imageParts = images.map(img => ({
        inlineData: {
          mimeType: "image/jpeg",
          data: img.split(',')[1]
        }
      }));

      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: [
          {
            parts: [
              { text: prompt },
              ...imageParts
            ]
          }
        ],
        config: {
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              type: { type: Type.STRING, enum: ["ID", "GOP", "PASSPORT"] },
              name: { type: Type.STRING },
              idNumber: { type: Type.STRING, description: "NIC Number or Passport Number" },
              gopNumber: { type: Type.STRING },
              expiryDate: { type: Type.STRING },
              dob: { type: Type.STRING },
              country: { type: Type.STRING },
              rotation: { type: Type.NUMBER },
              boundingBox: {
                type: Type.OBJECT,
                properties: {
                  ymin: { type: Type.NUMBER },
                  xmin: { type: Type.NUMBER },
                  ymax: { type: Type.NUMBER },
                  xmax: { type: Type.NUMBER }
                }
              }
            },
            required: ["type", "name", "expiryDate", "dob"]
          }
        }
      });

      const result = JSON.parse(response.text || "{}") as DocumentDetails;
      setDetails(result);

      // We crop the first image if it's the primary document AND it's an ID
      if (result.type === 'ID' && result.boundingBox && images[0]) {
        cropAndRotateImage(images[0], result.boundingBox, result.rotation || 0);
      } else {
        setCroppedImage(null);
      }

    } catch (err: any) {
      console.error("Error processing images:", err);
      let errorText = err?.message || String(err);
      if (typeof err === "object") {
        try {
          errorText += " | " + JSON.stringify(err);
        } catch (e) { }
      }
      setError("Error: " + errorText);
    } finally {
      setIsProcessing(false);
    }
  };

  const cropAndRotateImage = (base64: string, box: NonNullable<DocumentDetails['boundingBox']>, angleDegrees: number) => {
    const img = new Image();
    img.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const x = (box.xmin / 1000) * img.width;
      const y = (box.ymin / 1000) * img.height;
      const width = ((box.xmax - box.xmin) / 1000) * img.width;
      const height = ((box.ymax - box.ymin) / 1000) * img.height;

      canvas.width = width;
      canvas.height = height;

      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, width, height);

      ctx.save();
      ctx.translate(width / 2, height / 2);
      ctx.rotate((angleDegrees * Math.PI) / 180);
      ctx.drawImage(
        img,
        x, y, width, height,
        -width / 2, -height / 2, width, height
      );
      ctx.restore();

      setCroppedImage(canvas.toDataURL('image/jpeg', 0.9));
    };
    img.src = base64;
  };

  const cleanName = (name: string) => name.replace(/,/g, ' ').replace(/\s+/g, ' ').trim();

  const getOutputFields = () => {
    if (!details) return [];

    const name = cleanName(details.name);
    const acc = accountNumber || 'XXXXXXX';

    if (details.type === 'GOP') {
      return [
        { label: 'Verification', value: `Verified by Suraj - PP ${details.country || 'Unknown'} - GOP Expiry ${details.expiryDate}` },
        { label: 'PP Number', value: details.idNumber || 'Unknown' },
        { label: 'GOP Number', value: `GOP Number - ${details.gopNumber || 'Unknown'}` },
        { label: 'Birthday', value: details.dob },
        { label: 'Rename', value: `${name} ${acc} - GOP Expiry date ${details.expiryDate}` }
      ];
    }

    return [
      { label: 'Verification', value: `Verified by Suraj - NIC Expiry ${details.expiryDate}` },
      { label: 'NIC Number', value: details.idNumber || 'Unknown' },
      { label: 'Birthday', value: details.dob },
      { label: 'Rename', value: `${name} ${acc} - NIC Expiry date ${details.expiryDate}` }
    ];
  };

  const outputFields = getOutputFields();

  const copyLine = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const downloadFiles = () => {
    if (!details) return;

    const name = cleanName(details.name);
    const acc = accountNumber || 'XXXXXXX';
    const renameBase = details.type === 'GOP'
      ? `${name} ${acc} - GOP Expiry date ${details.expiryDate}`
      : `${name} ${acc} - NIC Expiry date ${details.expiryDate}`;

    if (details.type === 'ID' && croppedImage) {
      const link = document.createElement('a');
      link.href = croppedImage;
      link.download = `${renameBase}.jpg`;
      link.click();
    } else if (details.type === 'GOP') {
      images.forEach((img, idx) => {
        const link = document.createElement('a');
        link.href = img;
        const suffix = images.length > 1 ? `_${idx + 1}` : '';
        link.download = `${renameBase}${suffix}.jpg`;
        link.click();
      });
    }
  };

  const reset = () => {
    setImages([]);
    setCroppedImage(null);
    setDetails(null);
    setError(null);
    setAccountNumber('');
  };

  const removeImage = (idx: number) => {
    setImages(prev => prev.filter((_, i) => i !== idx));
    setDetails(null);
    setCroppedImage(null);
  };

  return (
    <div className="min-h-screen bg-[#F0F2F5] text-[#1C1E21] font-sans p-4 md:p-10">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <header className="mb-12 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="inline-block px-4 py-1.5 bg-blue-600 text-white text-[10px] font-bold uppercase tracking-[0.2em] rounded-full mb-4"
          >
            Enterprise Edition
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-4xl md:text-5xl font-extrabold tracking-tight text-[#050505] mb-3"
          >
            Identity Intelligence
          </motion.h1>
          <p className="text-base text-[#65676B] font-medium max-w-md mx-auto">
            Process NIC, GOP, and Passports with automated verification and straightening.
          </p>
        </header>

        <main className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Controls & Input */}
          <div className="lg:col-span-5 space-y-6">
            {/* Account Number Input */}
            <div className="bg-white rounded-3xl p-8 shadow-[0_2px_12px_rgba(0,0,0,0.08)] border border-black/5">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-1 h-4 bg-blue-600 rounded-full" />
                <label className="text-xs font-bold uppercase tracking-widest text-[#65676B]">
                  Account Configuration
                </label>
              </div>
              <input
                type="text"
                value={accountNumber}
                onChange={(e) => setAccountNumber(e.target.value)}
                placeholder="Enter account number..."
                className="w-full px-5 py-4 rounded-2xl bg-[#F0F2F5] border-transparent focus:bg-white focus:border-blue-500/30 focus:ring-4 focus:ring-blue-500/10 transition-all text-sm font-medium"
              />
            </div>

            {/* Upload Area */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              {...getRootProps()}
              className={cn(
                "relative group overflow-hidden border-2 border-dashed rounded-[2.5rem] p-12 text-center cursor-pointer transition-all duration-500",
                isDragActive ? "bg-blue-50 border-blue-400" : "bg-white border-black/10 hover:border-blue-400/50 hover:bg-blue-50/30"
              )}
            >
              <input {...getInputProps()} />
              <div className="flex flex-col items-center gap-4">
                <div className="w-16 h-16 rounded-3xl bg-blue-50 flex items-center justify-center group-hover:scale-110 transition-transform duration-500">
                  <Upload className="w-8 h-8 text-blue-600" />
                </div>
                <div>
                  <p className="text-xl font-bold text-[#050505]">Import Documents</p>
                  <p className="text-xs text-[#65676B] mt-1 font-medium">Upload NIC, GOP, or Passport (Max 2)</p>
                </div>
              </div>
            </motion.div>

            {/* Image Previews */}
            {images.length > 0 && (
              <div className="grid grid-cols-2 gap-4">
                {images.map((img, idx) => (
                  <div key={idx} className="relative aspect-[1.6/1] rounded-2xl overflow-hidden border border-black/5 bg-white shadow-sm">
                    <img src={img} className="w-full h-full object-contain" />
                    <button
                      onClick={() => removeImage(idx)}
                      className="absolute top-2 right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600 transition-colors"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}

            {images.length > 0 && !details && !isProcessing && (
              <button
                onClick={processImages}
                className="w-full py-4 bg-blue-600 text-white rounded-2xl font-bold text-sm uppercase tracking-widest hover:bg-blue-700 hover:shadow-lg hover:shadow-blue-600/20 active:scale-[0.98] transition-all flex items-center justify-center gap-3"
              >
                <RefreshCw className="w-4 h-4" />
                Process Documents
              </button>
            )}

            {isProcessing && (
              <div className="bg-white rounded-3xl p-8 shadow-sm border border-black/5 flex flex-col items-center gap-4 text-center">
                <Loader2 className="w-10 h-10 animate-spin text-blue-600" />
                <div>
                  <h3 className="text-lg font-bold">Analyzing Documents</h3>
                  <p className="text-xs text-[#65676B] mt-1">Gemini is extracting data and detecting edges...</p>
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-50 text-red-600 rounded-3xl p-6 shadow-sm border border-red-100 flex items-start gap-4">
                <AlertCircle className="w-6 h-6 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold">Error Processing</h3>
                  <p className="text-xs mt-1 text-red-500">{error}</p>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Output */}
          <div className="lg:col-span-7 space-y-6">
            <AnimatePresence mode="wait">
              {details ? (
                <motion.div
                  key="results"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="space-y-6"
                >
                  {/* Cropped Image Result */}
                  {croppedImage && (
                    <div className="bg-white rounded-[2.5rem] p-8 shadow-[0_4px_20px_rgba(0,0,0,0.06)] border border-black/5">
                      <div className="flex justify-between items-center mb-6">
                        <div className="flex items-center gap-2">
                          <div className="w-1 h-4 bg-emerald-500 rounded-full" />
                          <h2 className="text-xs font-bold uppercase tracking-widest text-[#65676B]">Straightened Output</h2>
                        </div>
                        <button
                          onClick={downloadFiles}
                          className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-emerald-600 hover:text-emerald-700 transition-colors"
                        >
                          <Download className="w-4 h-4" /> Save Image
                        </button>
                      </div>
                      <div className="aspect-[1.6/1] rounded-2xl overflow-hidden bg-white border border-black/5">
                        <img src={croppedImage} alt="Cropped" className="w-full h-full object-contain" referrerPolicy="no-referrer" />
                      </div>
                    </div>
                  )}

                  {/* Text Fields */}
                  <div className="space-y-4">
                    {details.type === 'GOP' && (
                      <div className="flex justify-end">
                        <button
                          onClick={downloadFiles}
                          className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-xl text-xs font-bold uppercase tracking-widest hover:bg-emerald-600 transition-all shadow-sm"
                        >
                          <Download className="w-4 h-4" /> Download GOP Files
                        </button>
                      </div>
                    )}
                    {outputFields.map((field, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="bg-white rounded-2xl p-6 shadow-sm border border-black/5 flex flex-col gap-2 group relative hover:shadow-md transition-shadow"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-1 h-3 bg-blue-600/30 rounded-full" />
                            <span className="text-[10px] font-bold uppercase tracking-widest text-[#65676B]">{field.label}</span>
                          </div>
                          <button
                            onClick={() => copyLine(field.value, idx)}
                            className={cn(
                              "p-2.5 rounded-xl transition-all",
                              copiedIndex === idx ? "bg-emerald-50 text-emerald-600" : "bg-[#F0F2F5] text-[#65676B] hover:bg-blue-50 hover:text-blue-600"
                            )}
                          >
                            {copiedIndex === idx ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                          </button>
                        </div>
                        <p className="text-base font-semibold text-[#050505] break-all pr-12">
                          {field.value}
                        </p>
                      </motion.div>
                    ))}
                  </div>

                  {/* Professional Preview */}
                  <div className="bg-[#1C1E21] text-white rounded-[2.5rem] p-10 shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-blue-600/10 blur-[100px] rounded-full -mr-32 -mt-32" />
                    <div className="relative z-10">
                      <div className="flex items-center gap-3 mb-8">
                        <FileText className="w-5 h-5 text-blue-400" />
                        <h3 className="text-xs font-bold uppercase tracking-[0.3em] text-blue-400">Final Verification Summary</h3>
                      </div>
                      <div className="space-y-6">
                        {outputFields.map((field, idx) => (
                          <div key={idx} className="border-l-2 border-white/10 pl-6 py-1">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-white/40 block mb-2">{field.label}</span>
                            <p className="text-lg font-medium tracking-tight text-white/90 leading-snug">{field.value}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : images.length === 0 ? (
                <div className="h-full min-h-[400px] flex flex-col items-center justify-center p-12 text-center border-2 border-dashed border-black/5 rounded-[2.5rem]">
                  <div className="w-20 h-20 rounded-full bg-white flex items-center justify-center mb-6 shadow-sm">
                    <AlertCircle className="w-10 h-10 text-black/10" />
                  </div>
                  <h3 className="text-xl font-bold text-[#050505]">Ready for Input</h3>
                  <p className="text-sm text-[#65676B] mt-2 max-w-[240px]">Upload NIC, GOP, or Passport images to begin.</p>
                </div>
              ) : !isProcessing ? (
                <div className="h-full min-h-[400px] flex flex-col items-center justify-center p-12 text-center bg-white rounded-[2.5rem] border border-black/5">
                  <div className="w-16 h-16 rounded-full bg-blue-50 flex items-center justify-center mb-4">
                    <RefreshCw className="w-8 h-8 text-blue-400" />
                  </div>
                  <h3 className="text-lg font-bold">Images Loaded</h3>
                  <p className="text-sm text-[#65676B] mt-2">Click "Process Documents" to start extraction.</p>
                </div>
              ) : null}
            </AnimatePresence>
          </div>
        </main>

        <canvas ref={canvasRef} className="hidden" />

        <footer className="mt-24 pt-10 border-t border-black/5 text-center">
          <p className="text-[10px] font-bold uppercase tracking-[0.4em] text-[#65676B]">Enterprise Identity Intelligence System</p>
        </footer>
      </div>
    </div>
  );
}
