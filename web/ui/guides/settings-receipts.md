# Receipts

How receipts are kept: encrypted in the data directory, each file once however often it is uploaded,
and in every backup.

## Largest file (MB) {#receipt-max-mb}

The largest receipt that can be uploaded, 25 MB by default. The file types are PDF, JPEG, PNG, WebP
and HEIC, checked from each file's content.

## Read receipts

MoneyKata reads each receipt's date, total and merchant on this server, with RapidOCR, and suggests
the transaction it belongs to. Nothing leaves the server, and no outside service or download is
involved. A PDF with text in it is read directly; a photo or scan is read by OCR. Turn it off on a
host too small to run it: receipts still upload and can be filled in by hand.

## Jobs at a time {#receipt-read-jobs}

How many receipts are read at once, each in its own process limited to 2 threads, a lower priority,
1.5 GB of memory and 60 seconds a receipt. A batch of uploads works through the queue.

## Reading

The queue: receipts waiting, read, and those that couldn't be read, with the reason on each.

## Re-read all receipts

After an update with new models: every receipt is read again. Only empty fields, and those still
holding what was read before, are replaced; anything a person typed stays.
