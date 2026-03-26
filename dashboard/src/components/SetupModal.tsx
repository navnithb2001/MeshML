import { useState, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { X, UploadCloud, Code, Settings, Play, CheckCircle } from 'lucide-react';
import { jobsAPI, datasetsAPI, modelsAPI } from '@/lib/api';
import { useToast } from '@/components/Toast';
import clsx from 'clsx';
import { useQuery } from '@tanstack/react-query';

interface SetupModalProps {
  isOpen: boolean;
  onClose: () => void;
}

function getErrorMessage(err: unknown, fallback: string): string {
  const candidate = err as {
    response?: { data?: { detail?: unknown; message?: unknown } };
  };
  const detail = candidate?.response?.data?.detail;
  const message = candidate?.response?.data?.message;

  if (Array.isArray(detail)) {
    const joined = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg?: unknown }).msg ?? '');
        }
        return '';
      })
      .filter(Boolean)
      .join(' | ');
    if (joined) return joined;
  }

  if (typeof detail === 'string' && detail.trim()) return detail;
  if (typeof message === 'string' && message.trim()) return message;
  return fallback;
}

export default function SetupModal({ isOpen, onClose }: SetupModalProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [targetVersion, setTargetVersion] = useState('');
  const [loading, setLoading] = useState(false);

  // File Upload State
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [datasetMode, setDatasetMode] = useState<'upload' | 'existing'>('upload');
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
  const [modelFile, setModelFile] = useState<File | null>(null);
  const [modelName, setModelName] = useState('');
  const [datasetId, setDatasetId] = useState<string | null>(null);

  const { groupId } = useParams<{ groupId: string }>();

  const datasetInputRef = useRef<HTMLInputElement>(null);
  const modelInputRef = useRef<HTMLInputElement>(null);

  const { data: datasets } = useQuery({
    queryKey: ['setup-modal-datasets'],
    queryFn: () => datasetsAPI.listDatasets(),
    enabled: isOpen,
  });

  if (!isOpen) return null;

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDatasetDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setDatasetFile(e.dataTransfer.files[0]);
    }
  };

  const handleModelDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setModelFile(e.dataTransfer.files[0]);
    }
  };

  const handleDataStepSubmit = async () => {
    if (datasetMode === 'existing') {
      if (!selectedDatasetId) {
        toast.warning('Select an existing dataset first.');
        return;
      }
      const selected = (datasets?.datasets || []).find((d) => d.id === selectedDatasetId);
      const selectedStatus = (selected?.status || '').toLowerCase();
      if (selected && !['available', 'uploaded'].includes(selectedStatus)) {
        toast.warning(`Dataset is ${selected.status}. Choose one that is available.`);
        return;
      }
      setDatasetId(selectedDatasetId);
      setStep(2);
      return;
    }

    if (!datasetFile) {
      toast.warning('Select a dataset file before continuing.');
      return;
    }
    setLoading(true);
    try {
      const res = await datasetsAPI.uploadDataset([datasetFile]);
      setDatasetId(res.dataset_id);
      setStep(2);
    } catch (err) {
      console.error('Failed to upload dataset', err);
      toast.error(getErrorMessage(err, 'Failed to upload dataset.'));
    } finally {
      setLoading(false);
    }
  };

  const handleCodeStepSubmit = async () => {
    if (!groupId) {
      toast.error('No Group Context found.');
      return;
    }
    if (!modelFile) {
      toast.warning('Upload a model file before continuing.');
      return;
    }
    if (!modelName.trim()) {
      toast.warning('Model Name is required when uploading architecture.');
      return;
    }
    setLoading(true);
    try {
      await modelsAPI.uploadModelArchitecture(modelFile, modelName, groupId);
      setStep(3);
      toast.success('Model architecture uploaded.');
    } catch (err) {
      console.error('Failed to upload model architecture', err);
      toast.error(getErrorMessage(err, 'Failed to upload model architecture.'));
    } finally {
      setLoading(false);
    }
  };

  const handleStartJob = async () => {
    if (!groupId) {
      toast.error('No Group Context found.');
      return;
    }
    const parsedTarget = targetVersion.trim() === '' ? 1000 : Number(targetVersion);
    if (!Number.isFinite(parsedTarget) || parsedTarget <= 0) {
      toast.warning('Convergence target must be a number greater than 0.');
      return;
    }
    setLoading(true);
    try {
      // POST /api/jobs (JobCreateRequest payload)
      const job = await jobsAPI.createJob({ 
        group_id: groupId,
        dataset_id: datasetId || undefined,
        config: { final_version: Math.floor(parsedTarget) }
      });
      // Immediately routes user to The Cockpit
      toast.success('Training run started successfully.');
      onClose();
      navigate(`/jobs/${job.id}/live`);
    } catch (err) {
      console.error('Failed to start job', err);
      toast.error(getErrorMessage(err, 'Failed to start training run.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm">
      <div className="w-full max-w-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 p-4 shrink-0">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-900 dark:text-slate-50">
            New Training Run
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-500">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 flex-1 max-h-[70vh] overflow-y-auto">
          {/* Step 1: Data */}
          {step === 1 && (
            <div className="space-y-4 animate-in fade-in zoom-in duration-200">
              <div className="text-xs font-mono uppercase text-slate-500 mb-2">Step 1/3: Data Ingestion</div>
              <div className="flex gap-2">
                <button
                  onClick={() => setDatasetMode('upload')}
                  className={clsx(
                    "text-xs font-medium uppercase tracking-wider px-3 py-2 border transition-colors",
                    datasetMode === 'upload'
                      ? "border-cyan-600 text-cyan-600 dark:border-cyan-400 dark:text-cyan-400"
                      : "border-slate-300 dark:border-slate-700 text-slate-500"
                  )}
                >
                  Upload New
                </button>
                <button
                  onClick={() => setDatasetMode('existing')}
                  className={clsx(
                    "text-xs font-medium uppercase tracking-wider px-3 py-2 border transition-colors",
                    datasetMode === 'existing'
                      ? "border-cyan-600 text-cyan-600 dark:border-cyan-400 dark:text-cyan-400"
                      : "border-slate-300 dark:border-slate-700 text-slate-500"
                  )}
                >
                  Use Existing
                </button>
              </div>

              {datasetMode === 'existing' && (
                <div className="border border-slate-200 dark:border-slate-800 p-4 max-h-72 overflow-y-auto">
                  {(!datasets?.datasets || datasets.datasets.length === 0) && (
                    <div className="text-sm font-mono text-slate-500">No previous datasets found.</div>
                  )}
                  <div className="space-y-2">
                    {(datasets?.datasets || []).map((dataset) => (
                      <button
                        key={dataset.id}
                        onClick={() => setSelectedDatasetId(dataset.id)}
                        className={clsx(
                          "w-full text-left border p-3 transition-colors",
                          selectedDatasetId === dataset.id
                            ? "border-cyan-600 bg-cyan-50/40 dark:bg-cyan-950/20"
                            : "border-slate-200 dark:border-slate-800 hover:border-cyan-500"
                        )}
                      >
                        <div className="text-sm font-medium text-slate-900 dark:text-slate-50">{dataset.name}</div>
                        <div className="text-xs font-mono text-slate-500 mt-1">{dataset.id}</div>
                        <div className="text-xs text-slate-500 mt-1 uppercase">{dataset.status}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {datasetMode === 'upload' && (
              <div 
                onDragOver={handleDragOver}
                onDrop={handleDatasetDrop}
                onClick={() => datasetInputRef.current?.click()}
                className={clsx(
                  "border border-dashed p-12 flex flex-col items-center justify-center cursor-pointer transition-colors group",
                  datasetFile 
                    ? "border-emerald-500 bg-emerald-50/10 dark:bg-emerald-950/20" 
                    : "border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 hover:border-cyan-500"
                )}
              >
                <input
                  ref={datasetInputRef}
                  type="file"
                  accept=".zip"
                  className="hidden"
                  onChange={(e) => { if (e.target.files?.[0]) setDatasetFile(e.target.files[0]); }}
                />
                {datasetFile ? (
                  <>
                    <CheckCircle className="w-8 h-8 text-emerald-500 mb-4" />
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-50">{datasetFile.name}</p>
                    <p className="text-xs text-slate-500 font-mono mt-2">{(datasetFile.size / 1024 / 1024).toFixed(2)} MB</p>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-8 h-8 text-slate-400 group-hover:text-cyan-500 mb-4 transition-colors" />
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-50">Drag & drop dataset here</p>
                    <p className="text-xs text-slate-500 font-mono mt-2">
                      Supported: .zip, imagefolder, csv, coco (auto-detected)
                    </p>
                  </>
                )}
              </div>
              )}
              <div className="flex justify-end pt-4">
                <button 
                  onClick={handleDataStepSubmit} 
                  disabled={loading}
                  className="bg-slate-900 dark:bg-slate-50 text-white dark:text-slate-900 text-sm font-medium py-2 px-6 disabled:opacity-50"
                >
                  {loading ? 'UPLOADING...' : 'NEXT'}
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Code */}
          {step === 2 && (
            <div className="space-y-4 animate-in fade-in zoom-in duration-200">
              <div className="text-xs font-mono uppercase text-slate-500 mb-2 flex justify-between">
                <span>Step 2/3: Model Architecture</span>
              </div>
              
              <div className="space-y-2">
                <label className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Model Reference Name
                </label>
                <input
                  type="text"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 p-2 font-mono text-sm placeholder:text-slate-400 focus:outline-none focus:border-cyan-600 dark:focus:border-cyan-400 transition-colors"
                  placeholder="e.g. gpt2-base-architecture"
                />
              </div>

              <div 
                onDragOver={handleDragOver}
                onDrop={handleModelDrop}
                onClick={() => modelInputRef.current?.click()}
                className={clsx(
                  "border border-dashed p-12 flex flex-col items-center justify-center cursor-pointer transition-colors group",
                  modelFile 
                    ? "border-emerald-500 bg-emerald-50/10 dark:bg-emerald-950/20" 
                    : "border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 hover:border-cyan-500"
                )}
              >
                <input
                  ref={modelInputRef}
                  type="file"
                  accept=".py"
                  className="hidden"
                  onChange={(e) => { if (e.target.files?.[0]) setModelFile(e.target.files[0]); }}
                />
                {modelFile ? (
                  <>
                    <CheckCircle className="w-8 h-8 text-emerald-500 mb-4" />
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-50">{modelFile.name}</p>
                    <p className="text-xs text-slate-500 font-mono mt-2">{(modelFile.size / 1024).toFixed(2)} KB</p>
                  </>
                ) : (
                  <>
                    <Code className="w-8 h-8 text-slate-400 group-hover:text-cyan-500 mb-4 transition-colors" />
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-50">Drag & drop model code here (.py)</p>
                  </>
                )}
              </div>
              <div className="flex justify-between pt-4">
                <button onClick={() => setStep(1)} disabled={loading} className="border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-50 text-sm font-medium py-2 px-6 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                  BACK
                </button>
                <button onClick={handleCodeStepSubmit} disabled={loading} className="bg-slate-900 dark:bg-slate-50 text-white dark:text-slate-900 text-sm font-medium py-2 px-6 disabled:opacity-50">
                   {loading ? 'UPLOADING...' : 'NEXT'}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Config */}
          {step === 3 && (
            <div className="space-y-4 animate-in fade-in zoom-in duration-200">
              <div className="text-xs font-mono uppercase text-slate-500 mb-2">Step 3/3: Configuration</div>
              <div className="border border-slate-200 dark:border-slate-800 p-6">
                <label className="flex items-center space-x-2 text-sm font-medium text-slate-900 dark:text-slate-50 mb-4 uppercase tracking-wider">
                  <Settings className="w-4 h-4 text-slate-500" />
                  <span>Convergence Target</span>
                </label>
                <div className="space-y-2">
                  <label className="text-xs font-mono text-slate-500">final_version (epochs/steps)</label>
                  <input 
                    type="number" 
                    value={targetVersion}
                    onChange={(e) => setTargetVersion(e.target.value)}
                    placeholder="e.g. 10000"
                    className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 p-2 font-mono text-sm focus:outline-none focus:border-cyan-600 dark:focus:border-cyan-400 transition-colors"
                  />
                </div>
              </div>
              
              <div className="flex justify-between pt-4">
                <button onClick={() => setStep(2)} disabled={loading} className="border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-50 text-sm font-medium py-2 px-6 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50">
                  BACK
                </button>
                <button onClick={handleStartJob} disabled={loading} className="bg-cyan-600 hover:bg-cyan-700 text-white text-sm font-medium py-2 px-6 flex items-center space-x-2 transition-colors disabled:opacity-50">
                  <Play className="w-4 h-4 fill-current" />
                  <span>{loading ? 'STARTING...' : 'START JOB'}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
