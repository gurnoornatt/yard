import { useCallback, useState } from 'react'
import { motion } from 'framer-motion'
import { Upload, FileText } from 'lucide-react'

export function DropZone({ onFile }: { onFile: (f: File) => void }) {
  const [dragging, setDragging] = useState(false)

  const handle = useCallback((file: File) => {
    if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) onFile(file)
  }, [onFile])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handle(file)
  }, [handle])

  const onInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handle(file)
  }, [handle])

  return (
    <motion.label
      animate={{ borderColor: dragging ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.08)' }}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className="relative flex flex-col items-center justify-center w-full max-w-md h-52 rounded-2xl border-2 border-dashed cursor-pointer transition-colors bg-white/[0.02] hover:bg-white/[0.04]"
    >
      <input type="file" accept=".pdf,application/pdf" className="sr-only" onChange={onInputChange} />
      <motion.div animate={{ scale: dragging ? 1.1 : 1 }} className="flex flex-col items-center gap-3 text-center px-6">
        <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center">
          {dragging ? <FileText className="text-white/60" size={22} /> : <Upload className="text-white/40" size={22} />}
        </div>
        <div>
          <p className="text-white/70 text-sm font-medium">{dragging ? 'Drop it' : 'Drop OM PDF here'}</p>
          <p className="text-white/25 text-xs mt-1">or click to browse</p>
        </div>
      </motion.div>
    </motion.label>
  )
}
