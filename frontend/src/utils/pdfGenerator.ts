import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

interface Message {
  role: 'user' | 'assistant';
  content: string | any[];
  timestamp: string;
}

interface CategoryBreakdown {
  category: string;
  description: string;
  materials_cost: number;
  labor_cost: number;
  total: number;
}

interface CostTier {
  id: string;
  name: string;
  badge: string;
  description: string;
  total_cost: number;
  cogs: number;
  markup_percentage: number;
  markup_amount: number;
  included_items: string[];
  detailed_breakdown: CategoryBreakdown[];
}

interface PDFProjectData {
  projectTitle: string | null;
  projectType: string | null;
  status: string;
  createdAt: string;
  zipCode: string | null;
  selectedTier: CostTier | null;
  images: string[];
  messages: Message[];
  homeownerName: string | null;
  homeownerEmail: string | null;
  homeownerPhone: string | null;
  contractorName: string | null;
  contractorEmail: string | null;
  contractorPhone: string | null;
  isUnlockView: boolean;
  token: string;
}

const PRIMARY_COLOR: [number, number, number] = [245, 158, 11]; // Amber-500
const SECONDARY_COLOR: [number, number, number] = [30, 58, 95]; // Navy-900
const TEXT_COLOR: [number, number, number] = [55, 65, 81]; // Gray-700
const LIGHT_BG: [number, number, number] = [249, 250, 251]; // Gray-50

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(amount);
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function extractTextFromMessage(content: string | any[]): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .filter(p => p.type === 'text')
      .map(p => p.text)
      .join('\n');
  }
  return '';
}

export async function generateProjectPDF(project: PDFProjectData): Promise<void> {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 15;
  const contentWidth = pageWidth - (margin * 2);
  let yPosition = margin;

  // Helper function to add new page if needed
  const checkPageBreak = (requiredSpace: number) => {
    if (yPosition + requiredSpace > pageHeight - margin) {
      doc.addPage();
      yPosition = margin;
      return true;
    }
    return false;
  };

  // Helper function for section headers
  const addSectionHeader = (title: string) => {
    checkPageBreak(15);
    doc.setFillColor(...PRIMARY_COLOR);
    doc.rect(margin, yPosition, contentWidth, 10, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text(title, margin + 3, yPosition + 7);
    yPosition += 15;
    doc.setTextColor(...TEXT_COLOR);
    doc.setFont('helvetica', 'normal');
  };

  // ==================== HEADER ====================
  // Logo and title
  doc.setFillColor(...PRIMARY_COLOR);
  doc.rect(0, 0, pageWidth, 35, 'F');

  doc.setTextColor(255, 255, 255);
  doc.setFontSize(24);
  doc.setFont('helvetica', 'bold');
  doc.text('🏠 RenovationTech', margin, 15);

  doc.setFontSize(12);
  doc.setFont('helvetica', 'normal');
  doc.text('Renovation Estimate Report', margin, 25);

  yPosition = 45;

  // ==================== PROJECT INFO ====================
  doc.setTextColor(...SECONDARY_COLOR);
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  const projectName = project.projectTitle || project.projectType || 'Renovation Project';
  doc.text(projectName, margin, yPosition);
  yPosition += 10;

  // Project details in a nice box
  doc.setFillColor(...LIGHT_BG);
  doc.roundedRect(margin, yPosition, contentWidth, 30, 3, 3, 'F');

  doc.setTextColor(...TEXT_COLOR);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');

  const infoY = yPosition + 7;
  doc.setFont('helvetica', 'bold');
  doc.text('Project Type:', margin + 5, infoY);
  doc.setFont('helvetica', 'normal');
  doc.text(project.projectType || 'N/A', margin + 35, infoY);

  doc.setFont('helvetica', 'bold');
  doc.text('Location:', margin + 5, infoY + 7);
  doc.setFont('helvetica', 'normal');
  doc.text(project.zipCode || 'N/A', margin + 35, infoY + 7);

  doc.setFont('helvetica', 'bold');
  doc.text('Status:', margin + 5, infoY + 14);
  doc.setFont('helvetica', 'normal');
  doc.text(project.status.toUpperCase(), margin + 35, infoY + 14);

  doc.setFont('helvetica', 'bold');
  doc.text('Created:', margin + 90, infoY);
  doc.setFont('helvetica', 'normal');
  doc.text(formatDate(project.createdAt), margin + 115, infoY);

  if (project.selectedTier) {
    doc.setFont('helvetica', 'bold');
    doc.text('Estimate:', margin + 90, infoY + 7);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...PRIMARY_COLOR);
    doc.text(formatCurrency(project.selectedTier.total_cost), margin + 115, infoY + 7);
    doc.setTextColor(...TEXT_COLOR);
  }

  doc.setFont('helvetica', 'bold');
  doc.text('Token:', margin + 90, infoY + 14);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.text(project.token, margin + 115, infoY + 14);
  doc.setFontSize(10);

  yPosition += 35;

  // ==================== PRICING BREAKDOWN ====================
  if (project.selectedTier) {
    addSectionHeader('Cost Estimate - ' + project.selectedTier.name);

    // Summary boxes
    doc.setFillColor(...LIGHT_BG);
    const boxWidth = (contentWidth - 10) / 3;

    // Total Cost box
    doc.roundedRect(margin, yPosition, boxWidth, 15, 2, 2, 'F');
    doc.setFontSize(8);
    doc.setTextColor(...TEXT_COLOR);
    doc.text('Total Cost', margin + 3, yPosition + 5);
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...PRIMARY_COLOR);
    doc.text(formatCurrency(project.selectedTier.total_cost), margin + 3, yPosition + 11);

    // COGS box
    doc.setFillColor(...LIGHT_BG);
    doc.roundedRect(margin + boxWidth + 5, yPosition, boxWidth, 15, 2, 2, 'F');
    doc.setFontSize(8);
    doc.setTextColor(...TEXT_COLOR);
    doc.setFont('helvetica', 'normal');
    doc.text('COGS', margin + boxWidth + 8, yPosition + 5);
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text(formatCurrency(project.selectedTier.cogs), margin + boxWidth + 8, yPosition + 11);

    // Markup box
    doc.setFillColor(...LIGHT_BG);
    doc.roundedRect(margin + (boxWidth + 5) * 2, yPosition, boxWidth, 15, 2, 2, 'F');
    doc.setFontSize(8);
    doc.setTextColor(...TEXT_COLOR);
    doc.setFont('helvetica', 'normal');
    doc.text('Markup', margin + (boxWidth + 5) * 2 + 3, yPosition + 5);
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text(`${project.selectedTier.markup_percentage}%`, margin + (boxWidth + 5) * 2 + 3, yPosition + 11);

    yPosition += 20;
    doc.setTextColor(...TEXT_COLOR);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);

    // Detailed breakdown table
    checkPageBreak(40);

    const tableData = project.selectedTier.detailed_breakdown.map(item => [
      item.category,
      formatCurrency(item.materials_cost),
      formatCurrency(item.labor_cost),
      formatCurrency(item.total)
    ]);

    // Add subtotal and total rows
    tableData.push(
      ['Subtotal (COGS)', '', '', formatCurrency(project.selectedTier.cogs)],
      [`Markup (${project.selectedTier.markup_percentage}%)`, '', '', formatCurrency(project.selectedTier.markup_amount)],
    );

    autoTable(doc, {
      startY: yPosition,
      head: [['Category', 'Materials', 'Labor', 'Total']],
      body: tableData,
      foot: [[{ content: 'Total Estimate', colSpan: 3, styles: { halign: 'right', fontStyle: 'bold' } }, formatCurrency(project.selectedTier.total_cost)]],
      theme: 'grid',
      headStyles: {
        fillColor: SECONDARY_COLOR,
        textColor: [255, 255, 255],
        fontSize: 10,
        fontStyle: 'bold'
      },
      footStyles: {
        fillColor: PRIMARY_COLOR,
        textColor: [255, 255, 255],
        fontSize: 11,
        fontStyle: 'bold'
      },
      styles: {
        fontSize: 9,
        cellPadding: 3
      },
      alternateRowStyles: {
        fillColor: LIGHT_BG
      },
      columnStyles: {
        0: { cellWidth: contentWidth * 0.4 },
        1: { cellWidth: contentWidth * 0.2, halign: 'right' },
        2: { cellWidth: contentWidth * 0.2, halign: 'right' },
        3: { cellWidth: contentWidth * 0.2, halign: 'right', fontStyle: 'bold' }
      },
      margin: { left: margin, right: margin }
    });

    yPosition = (doc as any).lastAutoTable.finalY + 10;

    // Included items
    if (project.selectedTier.included_items.length > 0) {
      checkPageBreak(30);
      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.text('Included Items:', margin, yPosition);
      yPosition += 7;

      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      const itemsPerRow = 2;
      const itemWidth = (contentWidth - 5) / itemsPerRow;

      project.selectedTier.included_items.forEach((item, idx) => {
        const col = idx % itemsPerRow;
        const row = Math.floor(idx / itemsPerRow);
        const x = margin + (col * (itemWidth + 5));
        const y = yPosition + (row * 6);

        checkPageBreak(10);
        doc.text(`• ${item}`, x, y);
      });

      const totalRows = Math.ceil(project.selectedTier.included_items.length / itemsPerRow);
      yPosition += totalRows * 6 + 5;
    }
  }

  // ==================== CONVERSATION SUMMARY ====================
  if (project.messages.length > 0) {
    addSectionHeader('Conversation Summary');

    doc.setFontSize(9);
    let messageCount = 0;
    const maxMessages = 10; // Limit to avoid too long PDFs

    for (const msg of project.messages) {
      if (messageCount >= maxMessages) {
        doc.setFont('helvetica', 'italic');
        doc.text(`... and ${project.messages.length - maxMessages} more messages`, margin, yPosition);
        yPosition += 7;
        break;
      }

      checkPageBreak(20);

      const text = extractTextFromMessage(msg.content);
      if (!text.trim()) continue;

      // Message header
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(...(msg.role === 'user' ? PRIMARY_COLOR : SECONDARY_COLOR));
      doc.text(msg.role === 'user' ? 'You:' : 'AI Assistant:', margin, yPosition);
      yPosition += 5;

      // Message content
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(...TEXT_COLOR);

      const lines = doc.splitTextToSize(text.substring(0, 500), contentWidth - 5);
      lines.forEach((line: string) => {
        checkPageBreak(7);
        doc.text(line, margin + 3, yPosition);
        yPosition += 5;
      });

      if (text.length > 500) {
        doc.setFont('helvetica', 'italic');
        doc.text('(truncated...)', margin + 3, yPosition);
        yPosition += 5;
      }

      yPosition += 3;
      messageCount++;
    }
  }

  // ==================== HOMEOWNER CONTACT (Contractor view only) ====================
  if (project.isUnlockView && (project.homeownerName || project.homeownerEmail || project.homeownerPhone)) {
    addSectionHeader('Homeowner Contact Information');

    doc.setFillColor(220, 252, 231); // Light green
    doc.roundedRect(margin, yPosition, contentWidth, 25, 3, 3, 'F');

    doc.setFontSize(10);
    doc.setTextColor(...TEXT_COLOR);
    let contactY = yPosition + 7;

    if (project.homeownerName) {
      doc.setFont('helvetica', 'bold');
      doc.text('Name:', margin + 5, contactY);
      doc.setFont('helvetica', 'normal');
      doc.text(project.homeownerName, margin + 25, contactY);
      contactY += 6;
    }

    if (project.homeownerEmail) {
      doc.setFont('helvetica', 'bold');
      doc.text('Email:', margin + 5, contactY);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(...PRIMARY_COLOR);
      doc.text(project.homeownerEmail, margin + 25, contactY);
      doc.setTextColor(...TEXT_COLOR);
      contactY += 6;
    }

    if (project.homeownerPhone) {
      doc.setFont('helvetica', 'bold');
      doc.text('Phone:', margin + 5, contactY);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(...PRIMARY_COLOR);
      doc.text(project.homeownerPhone, margin + 25, contactY);
      doc.setTextColor(...TEXT_COLOR);
    }

    yPosition += 30;
  }

  // ==================== FOOTER ====================
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);

    // Footer line
    doc.setDrawColor(...PRIMARY_COLOR);
    doc.setLineWidth(0.5);
    doc.line(margin, pageHeight - 15, pageWidth - margin, pageHeight - 15);

    // Footer text
    doc.setFontSize(8);
    doc.setTextColor(...TEXT_COLOR);
    doc.setFont('helvetica', 'normal');
    doc.text('Generated by RenovationTech', margin, pageHeight - 10);
    doc.text(`Page ${i} of ${totalPages}`, pageWidth - margin - 20, pageHeight - 10);

    doc.setFontSize(7);
    doc.setTextColor(150, 150, 150);
    doc.text(new Date().toLocaleDateString(), pageWidth / 2, pageHeight - 10, { align: 'center' });
  }

  // Save the PDF
  const fileName = `${(project.projectTitle || project.projectType || 'Project').replace(/\s+/g, '_')}_${project.token}.pdf`;
  doc.save(fileName);
}
