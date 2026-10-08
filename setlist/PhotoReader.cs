using System;
using System.Threading.Tasks;
using Windows.Storage;
using Windows.Storage.Streams;
using Windows.Graphics.Imaging;
using Windows.Media.Ocr;
class PhotoReader {
    static int Main(string[] args) {
        Console.OutputEncoding = new System.Text.UTF8Encoding(false);
        try { Console.Write(Read(args[0])); return 0; }
        catch(Exception e) { Console.Error.Write(e.Message); return 1; }
    }
    static T Wait<T>(Windows.Foundation.IAsyncOperation<T> op) { while(op.Status == Windows.Foundation.AsyncStatus.Started) System.Threading.Thread.Sleep(20); return op.GetResults(); }
    static string Read(string path) {
        var file = Wait<StorageFile>(StorageFile.GetFileFromPathAsync(path));
        using(var stream = Wait<IRandomAccessStream>(file.OpenAsync(FileAccessMode.Read))) {
            var decoder = Wait<BitmapDecoder>(BitmapDecoder.CreateAsync(stream));
            if(decoder.PixelWidth > 4000 || decoder.PixelHeight > 4000) throw new Exception("Use an image under 4000 pixels on each side.");
            using(var bitmap = Wait<SoftwareBitmap>(decoder.GetSoftwareBitmapAsync())) {
                var engine = OcrEngine.TryCreateFromUserProfileLanguages();
                if(engine == null) throw new Exception("Install a Windows OCR language pack or paste the song names.");
                var result = Wait<OcrResult>(engine.RecognizeAsync(bitmap));
                var lines = new System.Collections.Generic.List<string>();
                foreach(var line in result.Lines) lines.Add(line.Text);
                return string.Join("\n", lines);
            }
        }
    }
}
