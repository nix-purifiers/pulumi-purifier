package workspace

import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "fmt"
 "io"
 "os"
 "path/filepath"
 "sync"
)

var purifierMu sync.Mutex
var purifierURLs = map[string]string{}

func purifierCaptureHTTP(url string, body io.ReadCloser) (io.ReadCloser, error) {
 directory := os.Getenv("PULUMI_PURIFIER_CAPTURE")
 if directory == "" { return body, nil }
 defer body.Close()
 file, err := os.CreateTemp(directory, "response-")
 if err != nil { return nil, err }
 digest := sha256.New()
 _, err = io.Copy(io.MultiWriter(file, digest), body)
 file.Close()
 if err != nil { return nil, err }
 hash := hex.EncodeToString(digest.Sum(nil))
 destination := filepath.Join(directory, hash)
 if err = os.Rename(file.Name(), destination); err != nil { return nil, err }
 purifierMu.Lock()
 purifierURLs[hash] = url
 purifierMu.Unlock()
 return os.Open(destination)
}

func purifierCaptureArchive(spec PluginDescriptor, path string) error {
 directory := os.Getenv("PULUMI_PURIFIER_CAPTURE")
 if directory == "" { return nil }
 file, err := os.Open(path)
 if err != nil { return err }
 defer file.Close()
 digest := sha256.New()
 if _, err = io.Copy(digest, file); err != nil { return err }
 hash := hex.EncodeToString(digest.Sum(nil))
 purifierMu.Lock()
 defer purifierMu.Unlock()
 url := purifierURLs[hash]
 if url == "" { return fmt.Errorf("native plugin archive has no captured download URL") }
 record := map[string]interface{}{"spec":spec,"url":url,"sha256":hash,"archive":filepath.Join(directory,hash),"directory":spec.Dir()}
 output, err := os.OpenFile(filepath.Join(directory,"records.jsonl"),os.O_CREATE|os.O_WRONLY|os.O_APPEND,0600)
 if err != nil { return err }
 defer output.Close()
 return json.NewEncoder(output).Encode(record)
}
