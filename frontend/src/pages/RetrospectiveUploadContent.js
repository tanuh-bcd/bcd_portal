import React, { useState, useEffect, useRef, useCallback } from 'react';
import { FolderUp, RefreshCw, CheckCircle2, XCircle, Clock, AlertTriangle, ChevronDown, ChevronRight, Trash2 } from 'lucide-react';

const API_BASE = `${process.env.REACT_APP_API_URL || ''}/api/v1/admin/retrospective`;
const DICOM_EXTENSIONS = new Set(['dcm', 'dicom']);
const MAX_CONCURRENT_UPLOADS = 12;

const FILE_TYPE_FOLDER_NAMES = new Set([
  'dicom', 'dcm', 'dicoms', 'images', 'image', 'scan', 'scans',
  'report', 'reports', 'doc', 'docs', 'document', 'documents', 'pdf', 'pdfs',
]);

function authHeaders(extra = {}) {
  const token = localStorage.getItem('token');
  return { Authorization: `Bearer ${token}`, ...extra };
}

function classifyFileType(fileName) {
  const ext = fileName.includes('.') ? fileName.split('.').pop().toLowerCase() : '';
  return DICOM_EXTENSIONS.has(ext) ? 'DICOM' : 'REPORT';
}

function formatUploadedAt(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit',
  });
}

function groupFilesByCase(fileList) {
  const files = Array.from(fileList);
  if (files.length === 0) return { rootFolderName: '', caseMap: new Map() };

  const rootFolderName = files[0].webkitRelativePath.split('/')[0] || 'Retrospective_Data';

  const secondLevelFolderNames = new Set();
  for (const file of files) {
    const parts = file.webkitRelativePath.split('/');
    if (parts.length > 2) secondLevelFolderNames.add(parts[1]);
  }
  const allFileTypeFolders = Array.from(secondLevelFolderNames)
    .every((name) => FILE_TYPE_FOLDER_NAMES.has(name.toLowerCase()));
  const singleCaseMode = secondLevelFolderNames.size === 0 || allFileTypeFolders;

  const caseMap = new Map();
  let skippedCount = 0;

  for (const file of files) {
    const parts = file.webkitRelativePath.split('/');
    const fileName = parts[parts.length - 1];
    if (!fileName || fileName.startsWith('.')) continue;

    let caseName, sourceFolder;
    if (singleCaseMode) {
      if (parts.length < 2) continue;
      caseName = rootFolderName;
      sourceFolder = rootFolderName;
    } else {
      if (parts.length < 3) { skippedCount++; continue; }
      caseName = parts[1];
      sourceFolder = parts[1]; 
    }

    if (!caseMap.has(caseName)) {
      caseMap.set(caseName, { sourceFolder, files: [] });
    }
    caseMap.get(caseName).files.push({
      file_type: classifyFileType(fileName),
      file_name: fileName,
      fileObj: file,
    });
  }
  return { rootFolderName, caseMap, skippedCount };
}

async function runWithConcurrency(items, limit, worker, shouldStop) {
  const results = new Array(items.length);
  let next = 0;
  async function runner() {
    while (next < items.length) {
      if (shouldStop && shouldStop()) return;
      const i = next++;
      results[i] = await worker(items[i], i);
    }
  }
  await Promise.all(new Array(Math.min(limit, items.length)).fill(0).map(runner));
  return results;
}

function uploadFileWithProgress(uploadUrl, file, onProgress, onXhrCreated) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    if (onXhrCreated) onXhrCreated(xhr);
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    });
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`Upload failed: HTTP ${xhr.status}`));
    });
    xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
    xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));
    xhr.open('PUT', uploadUrl);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.send(file);
  });
}

const RetrospectiveUploadContent = () => {
  const [rootFolderName, setRootFolderName] = useState('');
  const [caseMap, setCaseMap] = useState(null); // Map caseName -> {sourceFolder, files:[{file_type,file_name,fileObj}]}
  const [creating, setCreating] = useState(false);
  const [activeBatch, setActiveBatch] = useState(null); // live progress for the batch currently uploading
  const [uploadStats, setUploadStats] = useState({ total: 0, done: 0 });
  const [error, setError] = useState(null);
  const [skippedCount, setSkippedCount] = useState(0);
  const [cancelling, setCancelling] = useState(false);
  const [batches, setBatches] = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [expandedBatchId, setExpandedBatchId] = useState(null);
  const [expandedCases, setExpandedCases] = useState([]);
  const [deleteTarget, setDeleteTarget] = useState(null); // batch pending delete confirmation
  const [deleting, setDeleting] = useState(false);
  const [historyMessage, setHistoryMessage] = useState(null); // { type: 'success'|'error', text }

  const cancelRequestedRef = useRef(false);
  const activeXhrsRef = useRef(new Set());
  const fileInputRef = useRef(null);
  const retryFileInputRef = useRef(null);
  const retryContextRef = useRef(null); // { uploadBatchId, filesToRetry }

  const fetchBatches = useCallback(async () => {
    setLoadingBatches(true);
    try {
      const res = await fetch(`${API_BASE}/batches`, { headers: authHeaders() });
      if (res.ok) setBatches(await res.json());
    } catch (e) {
      console.error('Failed to load retrospective batches', e);
    } finally {
      setLoadingBatches(false);
    }
  }, []);

  useEffect(() => { fetchBatches(); }, [fetchBatches]);

  const handleManualRefresh = () => {
    setExpandedBatchId(null);
    setExpandedCases([]);
    fetchBatches();
  };

  const refreshBatch = async (uploadBatchId) => {
    const res = await fetch(`${API_BASE}/batches/${uploadBatchId}`, { headers: authHeaders() });
    if (res.ok) {
      const updated = await res.json();
      setActiveBatch((prev) => (prev ? { ...prev, batch: updated } : prev));
      setBatches((prev) => prev.map((b) => (b.upload_batch_id === uploadBatchId ? updated : b)));
    }
  };

  const handleFolderSelect = (e) => {
    const { rootFolderName: root, caseMap: cm, skippedCount } = groupFilesByCase(e.target.files);
    if (cm.size === 0) {
      setError('No files found in the selected folder. Expected Case_XXX subfolders containing DICOM/report files.');
      return;
    }
    setRootFolderName(root);
    setCaseMap(cm);
    setError(null);
    setActiveBatch(null);
    setSkippedCount(skippedCount || 0);
  };

  const clearSelectedFolder = () => {
    setRootFolderName('');
    setCaseMap(null);
    setError(null);
    setSkippedCount(0);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const uploadFilesForCases = async (cases, fileLookup, batchId) => {
    // fileLookup: (sourceCaseName, file_name) -> File object
    const jobs = [];
    for (const c of cases) {
      for (const f of c.files) {
        if (f.upload_status === 'PENDING') {
          jobs.push({ sourceCaseName: c.source_case_name, fileId: f.id, fileName: f.file_name });
        }
      }
    }
    setUploadStats({ total: jobs.length, done: 0 });
    cancelRequestedRef.current = false;

    await runWithConcurrency(jobs, MAX_CONCURRENT_UPLOADS, async (job) => {
      const fileObj = fileLookup(job.sourceCaseName, job.fileName);
      let xhr = null;
      try {
        if (!fileObj) throw new Error('Local file not found (folder may have changed)');
        if (cancelRequestedRef.current) throw new Error('Upload cancelled');

        const urlRes = await fetch(`${API_BASE}/files/${job.fileId}/upload-url`, {
          method: 'POST',
          headers: authHeaders(),
        });
        if (!urlRes.ok) {
          const body = await urlRes.json().catch(() => ({}));
          throw new Error(body.detail || `Could not get upload URL (${urlRes.status})`);
        }
        const { upload_url, gcs_url } = await urlRes.json();

        await uploadFileWithProgress(upload_url, fileObj, null, (createdXhr) => {
          xhr = createdXhr;
          activeXhrsRef.current.add(xhr);
        });

        await fetch(`${API_BASE}/files/${job.fileId}/upload-complete`, {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ gcs_url }),
        });
      } catch (err) {
        await fetch(`${API_BASE}/files/${job.fileId}/upload-failed`, {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ error_message: err.message || 'Upload failed' }),
        }).catch(() => {});
      } finally {
        if (xhr) activeXhrsRef.current.delete(xhr);
        setUploadStats((prev) => ({ ...prev, done: prev.done + 1 }));
      }
    }, () => cancelRequestedRef.current);

    await refreshBatch(batchId);
    await fetchBatches();
  };

  const cancelUpload = () => {
    cancelRequestedRef.current = true;
    setCancelling(true);
    activeXhrsRef.current.forEach((xhr) => {
      try { xhr.abort(); } catch { /* already settled */ }
    });
    activeXhrsRef.current.clear();
  };

  const startUpload = async () => {
    if (!caseMap || caseMap.size === 0) return;
    setCreating(true);
    setError(null);
    try {
      const manifest = {
        source_folder_name: rootFolderName,
        cases: Array.from(caseMap.entries()).map(([sourceCaseName, data]) => ({
          source_case_name: sourceCaseName,
          source_folder: data.sourceFolder,
          files: data.files.map((f) => ({ file_type: f.file_type, file_name: f.file_name })),
        })),
      };

      const res = await fetch(`${API_BASE}/batches`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(manifest),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to create batch (${res.status})`);
      }
      const body = await res.json();
      setActiveBatch(body);
      await fetchBatches();

      const lookup = (sourceCaseName, fileName) => {
        const local = caseMap.get(sourceCaseName);
        if (!local) return null;
        const match = local.files.find((f) => f.file_name === fileName);
        return match ? match.fileObj : null;
      };

      await uploadFilesForCases(body.cases, lookup, body.batch.upload_batch_id);
      const wasCancelled = cancelRequestedRef.current;

      setCaseMap(null);
      setRootFolderName('');
      setSkippedCount(0);
      setActiveBatch(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (wasCancelled) {
        setError('Upload cancelled. Files already uploaded are safe; use "Resume Upload" on this batch in Upload History below to finish the rest.');
      }
    } catch (err) {
      setError(err.message || 'Failed to start upload');
    } finally {
      setCreating(false);
      setCancelling(false);
      cancelRequestedRef.current = false;
    }
  };

  const toggleBatchDetail = async (batch) => {
    if (expandedBatchId === batch.upload_batch_id) {
      setExpandedBatchId(null);
      setExpandedCases([]);
      return;
    }
    setExpandedBatchId(batch.upload_batch_id);
    try {
      const res = await fetch(`${API_BASE}/batches/${batch.upload_batch_id}/cases`, { headers: authHeaders() });
      setExpandedCases(res.ok ? await res.json() : []);
    } catch {
      setExpandedCases([]);
    }
    await refreshBatch(batch.upload_batch_id);
  };
  const refreshExpandedBatchCases = async () => {
    if (!expandedBatchId) return;
    try {
      const res = await fetch(`${API_BASE}/batches/${expandedBatchId}/cases`, { headers: authHeaders() });
      setExpandedCases(res.ok ? await res.json() : []);
    } catch {
      /* keep the stale list rather than clearing it on a transient error */
    }
    await refreshBatch(expandedBatchId);
  };

  const startRetry = async (batch) => {
    try {
      const res = await fetch(`${API_BASE}/batches/${batch.upload_batch_id}/retry`, {
        method: 'POST',
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error('Failed to start retry');
      const body = await res.json();
      if (body.files_to_retry.length === 0) {
        alert('Nothing left to upload for this batch.');
        return;
      }
      retryContextRef.current = { uploadBatchId: batch.upload_batch_id, filesToRetry: body.files_to_retry };
      alert(`Please reselect the "${batch.source_folder_name}" folder to finish ${body.files_to_retry.length} remaining file(s). Only those files will be uploaded -- everything already done is left untouched.`);
      retryFileInputRef.current?.click();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleRetryFolderSelect = async (e) => {
    const ctx = retryContextRef.current;
    if (!ctx) return;
    const { caseMap: cm } = groupFilesByCase(e.target.files);

    const lookup = (sourceCaseName, fileName) => {
      const local = cm.get(sourceCaseName);
      if (!local) return null;
      const match = local.files.find((f) => f.file_name === fileName);
      return match ? match.fileObj : null;
    };

    const jobs = ctx.filesToRetry.map((f) => ({ fileId: f.id, fileName: f.file_name, sourceCaseName: f.source_case_name }));
    setUploadStats({ total: jobs.length, done: 0 });
    await runWithConcurrency(jobs, MAX_CONCURRENT_UPLOADS, async (job) => {
      const fileObj = lookup(job.sourceCaseName, job.fileName);
      try {
        if (!fileObj) throw new Error('File not found in reselected folder');
        const urlRes = await fetch(`${API_BASE}/files/${job.fileId}/upload-url`, { method: 'POST', headers: authHeaders() });
        if (!urlRes.ok) throw new Error(`Could not get upload URL (${urlRes.status})`);
        const { upload_url, gcs_url } = await urlRes.json();
        await uploadFileWithProgress(upload_url, fileObj);
        await fetch(`${API_BASE}/files/${job.fileId}/upload-complete`, {
          method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ gcs_url }),
        });
      } catch (err) {
        await fetch(`${API_BASE}/files/${job.fileId}/upload-failed`, {
          method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ error_message: err.message }),
        }).catch(() => {});
      } finally {
        setUploadStats((prev) => ({ ...prev, done: prev.done + 1 }));
      }
    });

    await refreshBatch(ctx.uploadBatchId);
    await fetchBatches();
    retryContextRef.current = null;
    if (retryFileInputRef.current) retryFileInputRef.current.value = '';
  };

  const confirmDeleteBatch = (batch) => {
    setHistoryMessage(null);
    setDeleteTarget(batch);
  };

  const cancelDeleteBatch = () => {
    if (deleting) return;
    setDeleteTarget(null);
  };

  const performDeleteBatch = async () => {
    if (!deleteTarget) return;
    const batchId = deleteTarget.upload_batch_id;
    setDeleting(true);
    try {
      const res = await fetch(`${API_BASE}/batches/${batchId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to delete folder (${res.status})`);
      }
      setBatches((prev) => prev.filter((b) => b.upload_batch_id !== batchId));
      if (expandedBatchId === batchId) {
        setExpandedBatchId(null);
        setExpandedCases([]);
      }
      if (activeBatch?.batch?.upload_batch_id === batchId) setActiveBatch(null);
      setHistoryMessage({ type: 'success', text: 'Retrospective folder deleted successfully.' });
      setDeleteTarget(null);
    } catch (err) {
      setHistoryMessage({ type: 'error', text: err.message || 'Failed to delete folder. Please try again.' });
    } finally {
      setDeleting(false);
    }
  };

  const caseCount = caseMap ? caseMap.size : 0;
  const fileCount = caseMap ? Array.from(caseMap.values()).reduce((sum, c) => sum + c.files.length, 0) : 0;
  const totalCaseIdCount = batches.reduce((sum, b) => sum + (b.total_cases_identified || 0), 0);

  return (
    <div style={contentStyle}>
      <h2 style={{ color: '#14868C', marginTop: 0 }}>Retrospective Data Upload</h2>
      <p style={{ color: '#666', marginBottom: 24 }}>
        Bulk-upload a folder of historical cases (DICOM images and/or mammography reports) into the isolated
        retrospective store. This never creates BCD patient, questionnaire, or assessment records, and never
        touches the existing screening data.
      </p>

      <div style={panelStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <input
            ref={fileInputRef}
            type="file"
            webkitdirectory=""
            directory=""
            multiple
            onChange={handleFolderSelect}
            disabled={creating}
            style={{ display: 'none' }}
          />
          <button
            style={{ ...buttonStyle, opacity: creating ? 0.7 : 1 }}
            disabled={creating}
            onClick={() => fileInputRef.current?.click()}
          >
            <FolderUp size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Select Folder
          </button>

          {caseMap && (
            <span style={{ color: '#333', fontSize: 14 }}>
              Folder: <strong>{rootFolderName}</strong> &nbsp;—&nbsp; Total Case: <strong style={{ color: '#14868C' }}>{caseCount}</strong> &nbsp;({fileCount} file(s) detected)
            </span>
          )}

          {skippedCount > 0 && (
            <span style={{ color: '#c0392b', fontSize: 13 }}>
              {skippedCount} file(s) sat loose at the top of the folder (not inside any case subfolder) and were skipped.
            </span>
          )}

          {caseMap && !creating && (
            <button style={{ ...buttonStyle, backgroundColor: '#2f9e44' }} onClick={startUpload}>
              Start Upload
            </button>
          )}

          {caseMap && !creating && (
            <button style={{ ...buttonStyle, backgroundColor: '#fff', color: '#c0392b', border: '1.5px solid #c0392b' }} onClick={clearSelectedFolder}>
              Clear
            </button>
          )}
        </div>

        {creating && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 13, color: '#14868C' }}>
                {cancelling
                  ? 'Cancelling — finishing files already in progress…'
                  : uploadStats.total > 0
                    ? `Uploading files: ${uploadStats.done} / ${uploadStats.total}`
                    : 'Creating batch and identifying cases…'}
              </span>
              {uploadStats.total > 0 && !cancelling && (
                <button
                  style={{ ...iconButtonStyle, color: '#c0392b', borderColor: '#c0392b' }}
                  onClick={cancelUpload}
                >
                  Cancel Upload
                </button>
              )}
            </div>
            <ProgressBar percent={uploadStats.total ? Math.round((uploadStats.done / uploadStats.total) * 100) : 5} />
          </div>
        )}

        {error && <div style={{ color: '#dc3545', marginTop: 12, fontSize: 13 }}>{error}</div>}

        {activeBatch && (
          <div style={{ marginTop: 20 }}>
            <BatchSummary batch={activeBatch.batch} />
          </div>
        )}
      </div>

      <input
        ref={retryFileInputRef}
        type="file"
        webkitdirectory=""
        directory=""
        multiple
        onChange={handleRetryFolderSelect}
        style={{ display: 'none' }}
      />

      <div style={{ marginTop: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, flexWrap: 'wrap' }}>
            <h3 style={{ color: '#14868C', margin: 0 }}>Upload History</h3>
            <span style={{ fontSize: 14, color: '#333' }}>
              Total Retrospective Case Count: <strong style={{ color: '#14868C' }}>{totalCaseIdCount}</strong>
            </span>
          </div>
          <button style={iconButtonStyle} onClick={handleManualRefresh} title="Refresh">
            <RefreshCw size={16} />
          </button>
        </div>

        {historyMessage && (
          <div
            style={{
              marginTop: 12,
              padding: '8px 12px',
              borderRadius: 4,
              fontSize: 13,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              color: historyMessage.type === 'success' ? '#2f9e44' : '#c0392b',
              background: historyMessage.type === 'success' ? '#eafaf0' : '#fdecea',
              border: `1px solid ${historyMessage.type === 'success' ? '#b7e4c7' : '#f5c6cb'}`,
            }}
          >
            <span>{historyMessage.text}</span>
            <button
              style={{ ...iconButtonStyle, border: 'none', padding: '2px 6px' }}
              onClick={() => setHistoryMessage(null)}
            >
              ×
            </button>
          </div>
        )}

        {loadingBatches ? (
          <p style={{ color: '#999' }}>Loading…</p>
        ) : batches.length === 0 ? (
          <p style={{ color: '#999' }}>No retrospective uploads yet.</p>
        ) : (
          <div style={scrollWrapStyle}>
          <table style={{ ...tableStyle, minWidth: 760 }}>
            <thead>
              <tr>
                <th style={thStyle}></th>
                <th style={thStyle}>Batch ID</th>
                <th style={thStyle}>Folder</th>
                <th style={thStyle}>Total</th>
                <th style={thStyle}>Successful</th>
                <th style={thStyle}>Failed</th>
                <th style={thStyle}>Uploaded At</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}></th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <React.Fragment key={b.upload_batch_id}>
                  <tr>
                    <td style={tdStyle}>
                      <button style={iconButtonStyle} onClick={() => toggleBatchDetail(b)}>
                        {expandedBatchId === b.upload_batch_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>
                    </td>
                    <td style={tdStyle}>{b.upload_batch_id}</td>
                    <td style={tdStyle}>{b.source_folder_name}</td>
                    <td style={tdStyle}>{b.total_cases_identified}</td>
                    <td style={tdStyle}>{b.successful_cases}</td>
                    <td style={tdStyle}>{b.failed_cases}</td>
                    <td style={tdStyle}>{formatUploadedAt(b.created_at)}</td>
                    <td style={tdStyle}><StatusBadge status={b.batch_status} /></td>
                    <td style={tdStyle}>
                      {(() => {
                        const isActivelyUploadingHere = creating && activeBatch?.batch?.upload_batch_id === b.upload_batch_id;
                        const needsAction = b.failed_cases > 0 || b.batch_status === 'PENDING' || b.batch_status === 'PROCESSING';
                        return (
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {!isActivelyUploadingHere && needsAction && (
                              <button style={{ ...iconButtonStyle, color: '#c0392b' }} onClick={() => startRetry(b)}>
                                {b.failed_cases > 0 ? 'Retry Failed' : 'Resume Upload'}
                              </button>
                            )}
                            <button
                              style={{ ...iconButtonStyle, color: '#c0392b', opacity: isActivelyUploadingHere ? 0.5 : 1 }}
                              disabled={isActivelyUploadingHere}
                              title="Delete this folder and all its data"
                              onClick={() => confirmDeleteBatch(b)}
                            >
                              <Trash2 size={15} /> 
                            </button>
                          </div>
                        );
                      })()}
                    </td>
                  </tr>
                  {expandedBatchId === b.upload_batch_id && (
                    <tr>
                      <td colSpan={9} style={{ padding: 0, background: '#fafefe' }}>
                        <CaseTable cases={expandedCases} onCaseChanged={refreshExpandedBatchCases} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {deleteTarget && (
        <div style={modalOverlayStyle} onClick={cancelDeleteBatch}>
          <div style={modalBoxStyle} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginTop: 0, color: '#14868C' }}>Delete Retrospective Folder</h3>
            <p style={{ color: '#444', fontSize: 14 }}>
              Are you sure you want to delete <strong>"{deleteTarget.source_folder_name}"</strong> ({deleteTarget.upload_batch_id})
              and all its associated data? This will permanently remove its cases, files, and stored DICOM/report
              data. This cannot be undone.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
              <button
                style={{ ...buttonStyle, backgroundColor: '#fff', color: '#333', border: '1.5px solid #ccc' }}
                disabled={deleting}
                onClick={cancelDeleteBatch}
              >
                No, Cancel
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: '#c0392b', opacity: deleting ? 0.7 : 1 }}
                disabled={deleting}
                onClick={performDeleteBatch}
              >
                {deleting ? 'Deleting…' : 'Yes, Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const BatchSummary = ({ batch }) => (
  <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
    <StatTile label="Total Cases" value={batch.total_cases_identified} />
    <StatTile label="Processed" value={batch.processed_cases} />
    <StatTile label="Successful" value={batch.successful_cases} color="#2f9e44" />
    <StatTile label="Failed" value={batch.failed_cases} color="#c0392b" />
    <StatTile label="No Data" value={batch.no_data_cases} color="#999" />
    <div style={{ display: 'flex', alignItems: 'center' }}><StatusBadge status={batch.batch_status} /></div>
  </div>
);

const StatTile = ({ label, value, color = '#14868C' }) => (
  <div style={{ minWidth: 90 }}>
    <div style={{ fontSize: 22, fontWeight: 'bold', color }}>{value}</div>
    <div style={{ fontSize: 12, color: '#888' }}>{label}</div>
  </div>
);

const STATUS_META = {
  PENDING: { color: '#888', icon: Clock, label: 'Pending' },
  PROCESSING: { color: '#f39c12', icon: RefreshCw, label: 'Processing' },
  COMPLETED: { color: '#2f9e44', icon: CheckCircle2, label: 'Completed' },
  COMPLETED_WITH_ERRORS: { color: '#f39c12', icon: AlertTriangle, label: 'Completed with errors' },
  PARTIAL: { color: '#f39c12', icon: AlertTriangle, label: 'Partial' },
  FAILED: { color: '#c0392b', icon: XCircle, label: 'Failed' },
  NO_DATA: { color: '#999', icon: XCircle, label: 'No data' },
};

const StatusBadge = ({ status }) => {
  const meta = STATUS_META[status] || { color: '#666', icon: Clock, label: status };
  const Icon = meta.icon;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: meta.color, fontWeight: 600, fontSize: 13 }}>
      <Icon size={14} /> {meta.label}
    </span>
  );
};

const ProgressBar = ({ percent }) => (
  <div style={{ height: 8, background: '#e0e0e0', borderRadius: 4, overflow: 'hidden' }}>
    <div style={{ height: '100%', width: `${percent}%`, background: '#14868C', transition: 'width 0.3s' }} />
  </div>
);

const CaseTable = ({ cases, onCaseChanged }) => {
  const [caseDeleteTarget, setCaseDeleteTarget] = useState(null); // { retrospective_case_id, source_case_name }
  const [deletingCase, setDeletingCase] = useState(false);
  const [caseMessage, setCaseMessage] = useState(null);

  if (!cases || cases.length === 0) {
    return <div style={{ padding: 16, color: '#999', fontSize: 13 }}>No cases in this batch.</div>;
  }

  const confirmDeleteCase = (c) => {
    setCaseMessage(null);
    setCaseDeleteTarget(c);
  };

  const cancelDeleteCase = () => {
    if (deletingCase) return;
    setCaseDeleteTarget(null);
  };

  const performDeleteCase = async () => {
    if (!caseDeleteTarget) return;
    setDeletingCase(true);
    try {
      const res = await fetch(`${API_BASE}/cases/${caseDeleteTarget.retrospective_case_id}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to delete case (${res.status})`);
      }
      setCaseMessage({ type: 'success', text: `"${caseDeleteTarget.source_case_name}" deleted successfully.` });
      setCaseDeleteTarget(null);
      if (onCaseChanged) await onCaseChanged();
    } catch (err) {
      setCaseMessage({ type: 'error', text: err.message || 'Failed to delete case. Please try again.' });
    } finally {
      setDeletingCase(false);
    }
  };

  return (
    <div style={{ ...scrollWrapStyle, margin: '8px 16px', width: 'auto' }}>
      {caseMessage && (
        <div
          style={{
            marginBottom: 10,
            padding: '6px 10px',
            borderRadius: 4,
            fontSize: 12,
            color: caseMessage.type === 'success' ? '#2f9e44' : '#c0392b',
            background: caseMessage.type === 'success' ? '#eafaf0' : '#fdecea',
            border: `1px solid ${caseMessage.type === 'success' ? '#b7e4c7' : '#f5c6cb'}`,
          }}
        >
          {caseMessage.text}
        </div>
      )}
      <table style={{ ...tableStyle, minWidth: 600 }}>
        <thead>
          <tr>
            <th style={thStyle}>Case ID</th>
            <th style={thStyle}>Source Folder</th>
            <th style={thStyle}>DICOM</th>
            <th style={thStyle}>Report</th>
            <th style={thStyle}>Status</th>
            <th style={thStyle}>Error</th>
            <th style={thStyle}></th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr key={c.retrospective_case_id}>
              <td style={tdStyle}>{c.retrospective_case_id}</td>
              <td style={tdStyle}>{c.source_case_name}</td>
              <td style={tdStyle}>{c.dicom_available ? `${c.dicom_count} file(s)` : '—'}</td>
              <td style={tdStyle}>{c.report_available ? 'Available' : '—'}</td>
              <td style={tdStyle}><StatusBadge status={c.case_status} /></td>
              <td style={{ ...tdStyle, color: '#c0392b', maxWidth: 260 }}>{c.error_message || ''}</td>
              <td style={tdStyle}>
                <button
                  style={{ ...iconButtonStyle, color: '#c0392b' }}
                  title="Delete this source file (DICOM + report go with it)"
                  onClick={() => confirmDeleteCase(c)}
                >
                  <Trash2 size={12} /> 
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {caseDeleteTarget && (
        <div style={modalOverlayStyle} onClick={cancelDeleteCase}>
          <div style={modalBoxStyle} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginTop: 0, color: '#14868C' }}>Delete Source File</h3>
            <p style={{ color: '#444', fontSize: 14 }}>
              Are you sure you want to delete <strong>"{caseDeleteTarget.source_case_name}"</strong>{' '}
              ({caseDeleteTarget.retrospective_case_id})? Its DICOM images and report will be permanently removed
              from storage and from the database along with it. This cannot be undone.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
              <button
                style={{ ...buttonStyle, backgroundColor: '#fff', color: '#333', border: '1.5px solid #ccc' }}
                disabled={deletingCase}
                onClick={cancelDeleteCase}
              >
                No, Cancel
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: '#c0392b', opacity: deletingCase ? 0.7 : 1 }}
                disabled={deletingCase}
                onClick={performDeleteCase}
              >
                {deletingCase ? 'Deleting…' : 'Yes, Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const contentStyle = {
  backgroundColor: 'white',
  padding: 'clamp(16px, 4vw, 40px)',
  minHeight: '400px',
  color: '#666',
};

const panelStyle = {
  border: '1px solid #ddd',
  borderRadius: 8,
  padding: 'clamp(12px, 3vw, 20px)',
  background: '#fafefe',
};

// Lets a table scroll horizontally on narrow screens instead of squashing
// its columns unreadably or breaking the page layout.
const scrollWrapStyle = {
  width: '100%',
  overflowX: 'auto',
  WebkitOverflowScrolling: 'touch',
};

const buttonStyle = {
  padding: '10px 20px',
  backgroundColor: '#14868C',
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 'bold',
};

const iconButtonStyle = {
  background: 'none',
  border: '1px solid #ccc',
  borderRadius: 4,
  cursor: 'pointer',
  color: '#14868C',
  padding: '4px 8px',
  fontSize: 12,
  fontWeight: 600,
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
};

const tableStyle = {
  width: '100%',
  borderCollapse: 'collapse',
  marginTop: 12,
  fontSize: 13,
};

const thStyle = {
  textAlign: 'left',
  padding: '8px 10px',
  borderBottom: '2px solid #eee',
  color: '#333',
};

const tdStyle = {
  padding: '8px 10px',
  borderBottom: '1px solid #eee',
  color: '#444',
};

const modalOverlayStyle = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: 'rgba(0, 0, 0, 0.45)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
};

const modalBoxStyle = {
  background: 'white',
  borderRadius: 8,
  padding: 24,
  width: 'min(420px, 90vw)',
  boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
};

export default RetrospectiveUploadContent;
